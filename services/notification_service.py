import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from platforms.twitch_platform import TwitchPlatform
from platforms.tiktok_platform import TikTokPlatform
from datetime import datetime, timedelta
import traceback
from typing import Dict, Any, Optional
from enum import Enum
import discord
import logging

logger = logging.getLogger(__name__)

class ServiceStatus(Enum):
    RUNNING = "Running"
    STOPPED = "Stopped"
    ERROR = "Error"
    RECONNECTING = "Reconnecting"

class StreamCheckStatus:
    def __init__(self):
        self.last_check = None
        self.last_successful_check = None
        self.last_error = None
        self.consecutive_errors = 0
        self.status = ServiceStatus.STOPPED
        self.is_live = False
        self.error_count = 0
        self.success_count = 0
        self.guild_id = None

class NotificationService():
    DEFAULT_CHECK_INTERVALS = {
        'twitch': {
            "live": 1800,    # 30 minutes when stream is active
            "offline": 30,   # 30 seconds when stream is inactive
            "night": 1800    # 30 minutes in night mode
        }
    }

    def __init__(self, bot, config_service, logging_service):
        self.bot = bot
        self.config_service = config_service
        self.logging_service = logging_service
        self.platforms = {
            'twitch': TwitchPlatform(config_service),
            'tiktok': TikTokPlatform(config_service)
        }
        self.check_tasks = {}
        self._running = False
        self.service_status = ServiceStatus.STOPPED
        self.last_error = None
        self.start_time = None
        self.check_interval = 60  # sekundy
        self.main_task = None

    async def start_checking(self):
        """Start checking all stream statuses"""
        if self._running:
            return

        self._running = True
        logger.info("Starting stream status checking loop...")
        self.main_task = asyncio.create_task(self._check_streams_loop())
        logger.info("Stream status checking loop started")

    async def monitor_health(self):
        """Monitors checking tasks health and restarts them if needed"""
        while self._running:
            try:
                current_time = datetime.now()
                for task_key, task_info in self.check_tasks.items():
                    # Check if task is not responding (no activity for 5 minutes)
                    if (current_time - task_info['last_check']).total_seconds() > 300:
                        await self.logging_service.log_warning(
                            f"Task for {task_key} is not responding. Status: {task_info['status']}. Restarting...",
                            guild_id=task_info['guild_id']
                        )
                        # Cancel old task
                        if not task_info['task'].done():
                            task_info['task'].cancel()
                        
                        # Create new task
                        config = next(
                            (c for c in await self.config_service.get_all_configurations() 
                             if c['guild_id'] == task_info['guild_id'] and c['profile_url'] == task_key.split(':')[1]), 
                            None
                        )
                        if config:
                            new_task = asyncio.create_task(self.check_stream_loop(config))
                            self.check_tasks[task_key] = {
                                'task': new_task,
                                'last_check': current_time,
                                'status': 'restarted',
                                'guild_id': config['guild_id']
                            }
                            await self.logging_service.log_info(
                                f"Restarted task for {task_key}",
                                guild_id=config['guild_id']
                            )
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                await self.logging_service.log_error(e, "Error in task monitoring")
                await asyncio.sleep(30)

    async def check_stream_loop(self, config: Dict[str, Any]):
        """Check single stream with error handling and status tracking"""
        task_key = f"{config['guild_id']}:{config['profile_url']}"
        status = self.check_tasks.get(task_key)
        if not status:
            status = StreamCheckStatus()
            status.guild_id = config['guild_id']
            self.check_tasks[task_key] = status
        
        status.status = ServiceStatus.RUNNING
        platform = self.platforms.get(config['platform'].lower())
        
        if not platform:
            await self.logging_service.log_error(
                Exception(f"Unknown platform: {config['platform']}"),
                f"Guild ID: {config['guild_id']}",
                config['guild_id']
            )
            return

        # Get previous stream state from database
        previous_state = await self.config_service.get_stream_status(config['guild_id'], config['profile_url'])
        status.is_live = previous_state.get('is_live', False)

        while self._running:
            try:
                status.last_check = datetime.now()
                check_result = await platform.is_stream_live(config['profile_url'])
                print(f"[BUG] check_result: {check_result}")
                if isinstance(check_result, dict):
                    is_live = check_result.get('is_live', False)
                    error = check_result.get('error')
                    
                    if error:
                        if 'user not found' in str(error).lower():
                            await self.config_service.update_configuration_status(
                                config['guild_id'],
                                config['profile_url'],
                                False,
                                f"User not found: {error}"
                            )
                            await self.logging_service.log_warning(
                                f"Deactivating configuration for {config['profile_url']} - User not found",
                                config['guild_id']
                            )
                            break
                        
                        raise Exception(error)
                    
                    current_live_state = is_live
                else:
                    current_live_state = bool(check_result)

                status.last_successful_check = datetime.now()
                status.success_count += 1
                status.consecutive_errors = 0
                
                # Log check result
                await self.logging_service.log_debug(
                    f"Stream check result for {config['profile_url']}: {'Live' if current_live_state else 'Offline'}",
                    config['guild_id']
                )
                
                # Check if stream state changed from offline to online
                if current_live_state and not status.is_live:
                    await self.handle_stream_state_change(config, current_live_state)
                elif not current_live_state and status.is_live:
                    # Stream went offline
                    await self.logging_service.log_info(
                        f"Stream went offline: {config['profile_url']}",
                        config['guild_id']
                    )
                
                status.is_live = current_live_state
                # Update stream state in database
                await self.config_service.save_stream_state(
                    config['guild_id'],
                    config['profile_url'],
                    current_live_state
                )
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                status.error_count += 1
                status.consecutive_errors += 1
                status.last_error = str(e)
                
                await self.handle_check_error(config, e)
                
                # Exponential backoff for consecutive errors
                await asyncio.sleep(min(30 * (2 ** status.consecutive_errors), 300))

    async def handle_missing_channel(self, config):
        """Handle cases where notification channel is not found"""
        try:
            # Try to fetch channel information from Discord
            guild = self.bot.get_guild(config.get('guild_id'))
            if guild:
                # Check if channel exists with different ID
                channel = discord.utils.get(guild.channels, name=config.get('channel_name'))
                if channel:
                    # Update channel ID in config
                    config['channel_id'] = channel.id
                    await self.config_service.save_configuration(config)
                    await self.logging_service.log_info(
                        f"Updated channel ID for {config['profile_url']} to {channel.id}",
                        guild_id=config['guild_id']
                    )
                    return

            await self.logging_service.log_warning(
                f"Notification channel not found for {config['profile_url']}. "
                "Please reconfigure using /configure-notification",
                guild_id=config['guild_id']
            )
        except Exception as e:
            await self.logging_service.log_error(e, "Error handling missing channel", guild_id=config['guild_id'])

    async def handle_check_error(self, config: Dict[str, Any], error: Exception):
        """Handle stream check errors"""
        try:
            error_message = str(error)
            guild_id = config['guild_id']
            
            # Handle Twitch user not found error
            if "user not found" in error_message.lower():
                await self.config_service.update_configuration_status(
                    guild_id,
                    config['profile_url'],
                    False,
                    f"User not found: {error_message}"
                )
                
                await self.logging_service.log_warning(
                    f"Deactivating configuration for {config['profile_url']} - User not found",
                    guild_id
                )
                
                # Stop checking this stream
                task_key = f"{guild_id}:{config['profile_url']}"
                if task_key in self.check_tasks:
                    self.check_tasks[task_key]['task'].cancel()
                    del self.check_tasks[task_key]
                
                return

            # Log other errors
            await self.logging_service.log_error(
                error,
                f"Error checking stream {config['profile_url']}",
                guild_id
            )

        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error handling check error for {config['profile_url']}",
                config.get('guild_id')
            )

    async def handle_stream_state_change(self, config: Dict[str, Any], current_live_state: bool):
        """Handle stream state changes and send notifications"""
        try:
            guild_id = config['guild_id']
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                await self.logging_service.log_error(
                    Exception(f"Could not find guild {guild_id}"),
                    f"Guild not found",
                    guild_id
                )
                return

            channel = guild.get_channel(config['channel_id'])
            if not channel:
                await self.handle_missing_channel(config)
                return

            if current_live_state:  # Stream went live
                role = guild.get_role(config['role_id'])
                if not role:
                    await self.logging_service.log_error(
                        Exception(f"Could not find role {config['role_id']} in guild {guild_id}"),
                        f"Role not found",
                        guild_id
                    )
                    return

                embed = discord.Embed(
                    title="Stream is Live!",
                    description=config['message'],
                    color=discord.Color.green(),
                    url=config['profile_url']
                )
                
                embed.add_field(
                    name="Platform", 
                    value=config['platform'].capitalize(),
                    inline=True
                )
                
                embed.add_field(
                    name="Channel",
                    value=f"[Link]({config['profile_url']})",
                    inline=True
                )

                embed.timestamp = datetime.now()
                
                await channel.send(f"{role.mention}", embed=embed)
                
                await self.logging_service.log_info(
                    f"Stream went live notification sent\n"
                    f"Guild: {guild.name} ({guild_id})\n"
                    f"Channel: {channel.name}\n"
                    f"Stream: {config['profile_url']}",
                    guild_id
                )

            # Update stream state in database
            await self.config_service.save_stream_state(
                guild_id,
                config['profile_url'],
                current_live_state
            )

        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error handling stream state change for {config['profile_url']} in guild {config.get('guild_id')}",
                config.get('guild_id')
            )

    async def get_service_status(self) -> Dict[str, Any]:
        """Get detailed service status information"""
        return {
            "service": {
                "status": self.service_status.value,
                "uptime": str(datetime.now() - self.start_time) if self.start_time else "Not started",
                "last_error": str(self.last_error) if self.last_error else None
            },
            "streams": {
                task_key: {
                    "status": status.status.value,
                    "last_check": status.last_check.isoformat() if status.last_check else None,
                    "last_successful_check": status.last_successful_check.isoformat() if status.last_successful_check else None,
                    "is_live": status.is_live,
                    "error_count": status.error_count,
                    "success_count": status.success_count,
                    "consecutive_errors": status.consecutive_errors,
                    "last_error": status.last_error
                } for task_key, status in self.check_tasks.items()
            },
            "configurations": await self.config_service.get_all_configurations()
        }

    async def stop_checking(self):
        """Stop checking all stream statuses"""
        self._running = False
        self.service_status = ServiceStatus.STOPPED
        
        if self.main_task and not self.main_task.done():
            self.main_task.cancel()
            try:
                await self.main_task
            except asyncio.CancelledError:
                pass
        
        for task_key, task_info in self.check_tasks.items():
            try:
                if not task_info['task'].done():
                    task_info['task'].cancel()
                    await task_info['task']  # Wait for task to be cancelled
                if task_key in self.check_tasks:
                    self.check_tasks[task_key].status = ServiceStatus.STOPPED
            except asyncio.CancelledError:
                pass  # Expected when cancelling tasks
            except Exception as e:
                await self.logging_service.log_error(e, f"Error while stopping task for {task_key}", guild_id=task_info['guild_id'])
        
        self.check_tasks.clear()
        await self.logging_service.log_info("All checking tasks have been stopped")

    async def reload_configuration(self):
        """Reload service configuration and restart checking tasks"""
        print("Reloading notification service configuration...")
        try:
            # Stop existing tasks
            await self.stop_checking()
            
            # Clear existing tasks and statuses
            self.check_tasks.clear()
            
            # Start checking with new configuration
            await self.start_checking()
            
            await self.logging_service.log_info("Notification service configuration reloaded successfully")
        except Exception as e:
            await self.logging_service.log_error(e, "Error reloading notification service configuration")
            raise

    async def add_new_configuration(self, config):
        """Add new configuration and start checking"""
        try:
            print(f"Adding new configuration for {config['profile_url']}")
            
            task_key = f"{config['guild_id']}:{config['profile_url']}"
            if task_key not in self.check_tasks:
                # Create new checking task
                task = asyncio.create_task(self.check_stream_loop(config))
                self.check_tasks[task_key] = {
                    'task': task,
                    'last_check': datetime.now(),
                    'status': 'running',
                    'guild_id': config['guild_id']
                }
                
                # Initialize stream status
                status = StreamCheckStatus()
                status.status = ServiceStatus.RUNNING
                status.guild_id = config['guild_id']
                self.check_tasks[task_key] = status
                
                await self.logging_service.log_info(
                    f"Started checking for new configuration: {config['profile_url']}",
                    guild_id=config['guild_id']
                )
            else:
                await self.logging_service.log_info(
                    f"Configuration already exists for {config['profile_url']}",
                    guild_id=config['guild_id']
                )
        
        except Exception as e:
            await self.logging_service.log_error(
                e, 
                f"Error adding new configuration for {config['profile_url']}",
                guild_id=config['guild_id']
            )
            raise

    async def send_notification(self, config):
        """Sends notification with error handling"""
        try:
            channel = self.bot.get_channel(config['channel_id'])
            if channel:
                message = f"<@&{config['role_id']}> {config['message']}\n{config['profile_url']}"
                await channel.send(message)
                await self.logging_service.log_info(
                    f"Sent notification\n"
                    f"Channel: {channel.name}\n"
                    f"Stream: {config['profile_url']}",
                    guild_id=config['guild_id']
                )
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error while sending notification\n"
                f"Channel: {config.get('channel_id')}\n"
                f"Stream: {config['profile_url']}",
                guild_id=config['guild_id']
            )

    async def remove_configuration(self, guild_id: int, username: str, platform: str):
        """Remove configuration from notification service"""
        try:
            config_key = f"{guild_id}_{platform}_{username}"
            if config_key in self.check_tasks:
                task = self.check_tasks[config_key]
                if not task.done():
                    task.cancel()
                del self.check_tasks[config_key]
                
            await self.logging_service.log_info(
                f"Removed configuration for {platform} streamer: {username}",
                guild_id
            )
            
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error removing configuration for {platform} streamer: {username}",
                guild_id
            )
            raise

    async def handle_configuration_toggle(self, guild_id: int, profile_url: str, enable: bool):
        """Handle configuration enable/disable"""
        task_key = f"{guild_id}:{profile_url}"
        
        if enable:
            if task_key not in self.check_tasks:
                config = await self.config_service.get_configuration(guild_id, profile_url)
                if config:
                    task = asyncio.create_task(self.check_stream_loop(config))
                    self.check_tasks[task_key] = {
                        'task': task,
                        'last_check': datetime.now(),
                        'status': 'running',
                        'guild_id': guild_id
                    }
        else:
            if task_key in self.check_tasks:
                self.check_tasks[task_key]['task'].cancel()
                del self.check_tasks[task_key]

    async def update_configuration(self, config: Dict[str, Any]):
        """Update existing stream checking configuration"""
        try:
            task_key = f"{config['guild_id']}:{config['profile_url']}"
            
            # Stop existing task
            if task_key in self.check_tasks:
                task_info = self.check_tasks[task_key]
                if not task_info['task'].done():
                    task_info['task'].cancel()
            
            # Update configuration in database
            await self.config_service.save_configuration(config)
            
            # Start new task with updated config
            task = asyncio.create_task(self.check_stream_loop(config))
            self.check_tasks[task_key] = {
                'task': task,
                'last_check': datetime.now(),
                'status': 'running',
                'guild_id': config['guild_id']
            }
            
            await self.logging_service.log_info(
                f"Updated configuration for {config['profile_url']}",
                guild_id=config['guild_id']
            )
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error updating configuration for {config['profile_url']}",
                guild_id=config['guild_id']
            )
            raise

    async def add_configuration(self, config: Dict[str, Any]):
        """Add new configuration to notification service"""
        try:
            guild_id = config['guild_id']
            platform = config['platform']
            username = config['username']
            
            config_key = f"{guild_id}_{platform}_{username}"
            
            if config_key in self.check_tasks:
                old_task = self.check_tasks[config_key]
                if not old_task.done():
                    old_task.cancel()
            
            if self._running:
                await self._check_single_stream_status(config)
            
            await self.logging_service.log_info(
                f"Added configuration for {platform} streamer: {username}",
                guild_id
            )
            
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error adding configuration for {config.get('platform', 'unknown')} streamer: {config.get('username', 'unknown')}",
                config.get('guild_id')
            )
            raise

    async def _check_streams_loop(self):
        """Main loop for checking all stream statuses"""
        while self._running:
            try:
                logger.info("Checking all stream statuses...")
                configs = await self.config_service.get_all_configurations()
                
                for config in configs:
                    if not self._running:
                        break
                    
                    try:
                        await self._check_single_stream_status(config)
                    except Exception as e:
                        await self.logging_service.log_error(
                            e,
                            f"Error checking single stream status for {config['platform']} streamer: {config['username']}",
                            config['guild_id']
                        )
                
                logger.info("Finished checking all stream statuses")
                await asyncio.sleep(self.check_interval)
                
            except asyncio.CancelledError:
                logger.info("Stream status checking loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in stream status checking loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def _check_single_stream_status(self, config: Dict[str, Any]):
        """Check stream status once"""
        try:
            guild_id = config['guild_id']
            platform = config['platform']
            username = config['username']
            profile_url = config.get('profile_url', username)  # używamy profile_url jeśli istnieje, w przeciwnym razie username
            
            logger.info(f"Checking status for {platform} streamer: {username}")
            
            # Pobierz odpowiednią platformę
            platform_service = self.platforms.get(platform.lower())
            if not platform_service:
                raise ValueError(f"Unsupported platform: {platform}")
            
            # Sprawdź status streama używając odpowiedniej platformy
            try:
                # Użyj profile_url zamiast samego username
                status = await platform_service.is_stream_live(profile_url)
                print(f"[BUG2] status: {status}")
                # Sprawdź czy mamy do czynienia ze słownikiem czy wartością boolean
                if isinstance(status, dict):
                    is_live = status.get('is_live', False)
                    error_message = status.get('error')
                    # Zmiana logiki - konfiguracja jest aktywna, chyba że wystąpił błąd "user not found"
                    is_active = True
                    if error_message and 'user not found' in str(error_message).lower():
                        is_active = False
                else:
                    is_live = bool(status)
                    error_message = None
                    is_active = True
                    
            except Exception as platform_error:
                logger.error(f"Platform error for {platform} streamer {username}: {str(platform_error)}")
                is_live = False
                error_message = str(platform_error)
                # Nie ustawiamy is_active na False przy każdym błędzie
                is_active = True
            
            # Aktualizuj status w bazie danych
            await self.config_service.db_service.save_stream_state(guild_id, platform, username, is_live)
            
            # Aktualizuj status konfiguracji tylko jeśli mamy błąd "user not found"
            if not is_active or error_message:
                await self.config_service.db_service.update_configuration_status(
                    guild_id, 
                    platform, 
                    username, 
                    is_active,
                    error_message
                )
            
            # Jeśli streamer jest live, wyślij powiadomienie
            if is_live:
                await self._send_notification(config)
            
            logger.info(f"Status updated for {platform} streamer: {username} (live: {is_live}, active: {is_active})")
            
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error in single stream status check for {config['platform']} streamer: {config['username']}",
                config['guild_id']
            )
            
            # Aktualizuj status konfiguracji z błędem tylko w przypadku poważnych błędów
            await self.config_service.db_service.update_configuration_status(
                config['guild_id'],
                config['platform'],
                config['username'],
                True,  # Zostawiamy konfigurację aktywną
                str(e)  # error_message
            )

    async def _send_notification(self, config: Dict[str, Any]):
        """Send stream notification to Discord channel"""
        try:
            channel = self.bot.get_channel(config['channel_id'])
            if not channel:
                logger.error(f"Channel {config['channel_id']} not found")
                return

            # Sprawdź czy już wysłano powiadomienie
            last_status = await self.config_service.get_stream_status(
                config['guild_id'],
                config['platform'],
                config['username']
            )
            
            # Jeśli poprzedni status też był live, nie wysyłaj powiadomienia
            if last_status and last_status.get('is_live'):
                return

            # Przygotuj i wyślij wiadomość
            message = config['message']
            if config['platform'] == 'twitch':
                url = f"https://twitch.tv/{config['username']}"
            else:  # tiktok
                url = f"https://tiktok.com/@{config['username']}"

            await channel.send(f"{message}\n{url}")
            
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error sending notification for {config['platform']} streamer: {config['username']}",
                config['guild_id']
            ) 