import asyncio
from .platforms.tiktok_platform import TikTokPlatform
from .platforms.twitch_platform import TwitchPlatform
from datetime import datetime, timedelta
import traceback
from typing import Dict, Any
from enum import Enum
import discord

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

class NotificationService():
    DEFAULT_CHECK_INTERVALS = {
        'twitch': {
            "live": 1800,    # 30 minutes when stream is active
            "offline": 30,   # 30 seconds when stream is inactive
            "night": 1800    # 30 minutes in night mode
        }
    }

    def __init__(self, client, config_service, logging_service):
        self.client = client
        self.config_service = config_service
        self.logging_service = logging_service
        self.platforms = {
            'tiktok': TikTokPlatform(config_service),
            'twitch': TwitchPlatform(config_service)
        }
        self.checking_tasks = {}
        self.stream_statuses: Dict[str, StreamCheckStatus] = {}
        self.is_running = False
        self.service_status = ServiceStatus.STOPPED
        self.last_error = None
        self.start_time = None

    async def start_checking(self):
        """Starts stream checking with error handling and monitoring"""
        await self.logging_service.log_info("Starting stream checking service")
        self.is_running = True
        self.service_status = ServiceStatus.RUNNING
        self.start_time = datetime.now()
        
        try:
            configs = self.config_service.get_all_configurations()
            for config in configs:
                if config['profile_url'] not in self.checking_tasks:
                    task = asyncio.create_task(self.check_stream_loop(config))
                    self.checking_tasks[config['profile_url']] = {
                        'task': task,
                        'last_check': datetime.now(),
                        'status': 'running'
                    }
                    # Initialize stream status
                    if config['profile_url'] not in self.stream_statuses:
                        self.stream_statuses[config['profile_url']] = StreamCheckStatus()
                        self.stream_statuses[config['profile_url']].status = ServiceStatus.RUNNING
                    
                    await self.logging_service.log_debug(
                        f"Started checking for {config['profile_url']}"
                    )
        
        except Exception as e:
            self.service_status = ServiceStatus.ERROR
            self.last_error = str(e)
            self.is_running = False
            await self.logging_service.log_error(e, "Error while starting stream checks")
            raise

    async def monitor_health(self):
        """Monitors checking tasks health and restarts them if needed"""
        while self.is_running:
            try:
                current_time = datetime.now()
                for url, task_info in self.checking_tasks.items():
                    # Check if task is not responding (no activity for 5 minutes)
                    if (current_time - task_info['last_check']).total_seconds() > 300:
                        await self.logging_service.log_warning(
                            f"Task for {url} is not responding. Status: {task_info['status']}. Restarting..."
                        )
                        # Cancel old task
                        if not task_info['task'].done():
                            task_info['task'].cancel()
                        
                        # Create new task
                        config = next(
                            (c for c in self.config_service.get_all_configurations() 
                             if c['profile_url'] == url), 
                            None
                        )
                        if config:
                            new_task = asyncio.create_task(self.check_stream_loop(config))
                            self.checking_tasks[url] = {
                                'task': new_task,
                                'last_check': current_time,
                                'status': 'restarted'
                            }
                            await self.logging_service.log_info(
                                f"Restarted task for {url}"
                            )
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                await self.logging_service.log_error(e, "Error in task monitoring")
                await asyncio.sleep(30)

    async def check_stream_loop(self, config):
        """Check single stream with error handling and status tracking"""
        stream_status = self.stream_statuses.setdefault(config['profile_url'], StreamCheckStatus())
        stream_status.status = ServiceStatus.RUNNING
        
        while self.is_running:
            try:
                stream_status.last_check = datetime.now()
                platform = self.platforms.get(config['platform'])
                
                if not platform:
                    raise ValueError(f"Unsupported platform: {config['platform']}")

                # Check if channel still exists
                channel = self.client.get_channel(config['channel_id'])
                if not channel:
                    await self.handle_missing_channel(config)
                    continue

                current_live_state = await platform.is_stream_live(config['profile_url'])
                stream_status.last_successful_check = datetime.now()
                stream_status.consecutive_errors = 0
                stream_status.success_count += 1
                stream_status.is_live = current_live_state

                if current_live_state != config.get('is_live', False):
                    await self.handle_stream_state_change(config, current_live_state)

                check_interval = self.config_service.get_check_interval(config)
                await asyncio.sleep(check_interval)

            except asyncio.CancelledError:
                stream_status.status = ServiceStatus.STOPPED
                raise
            except Exception as e:
                stream_status.error_count += 1
                stream_status.consecutive_errors += 1
                stream_status.last_error = str(e)
                stream_status.status = ServiceStatus.ERROR

                await self.handle_check_error(config, e)
                
                # Exponential backoff for consecutive errors
                retry_delay = min(30 * (2 ** stream_status.consecutive_errors), 300)  # Max 5 minutes
                await asyncio.sleep(retry_delay)

    async def handle_missing_channel(self, config):
        """Handle cases where notification channel is not found"""
        try:
            # Try to fetch channel information from Discord
            guild = self.client.get_guild(config.get('guild_id'))
            if guild:
                # Check if channel exists with different ID
                channel = discord.utils.get(guild.channels, name=config.get('channel_name'))
                if channel:
                    # Update channel ID in config
                    config['channel_id'] = channel.id
                    self.config_service.save_configuration(config)
                    await self.logging_service.log_info(
                        f"Updated channel ID for {config['profile_url']} to {channel.id}"
                    )
                    return

            await self.logging_service.log_warning(
                f"Notification channel not found for {config['profile_url']}. "
                "Please reconfigure using /configure-notification"
            )
        except Exception as e:
            await self.logging_service.log_error(e, "Error handling missing channel")

    async def handle_check_error(self, config, error):
        """Handle stream check errors with appropriate actions"""
        status = self.stream_statuses[config['profile_url']]
        
        error_message = (
            f"Error checking stream {config['profile_url']}\n"
            f"Consecutive errors: {status.consecutive_errors}\n"
            f"Total errors: {status.error_count}\n"
            f"Error: {str(error)}\n"
            f"Stacktrace:\n{traceback.format_exc()}"
        )
        
        if status.consecutive_errors >= 5:
            error_message += "\nMultiple consecutive errors detected. Stream checking may be impaired."
        
        await self.logging_service.log_error(error, error_message)

    async def handle_stream_state_change(self, config, current_live_state):
        """Handle stream state changes and send notifications"""
        try:
            if current_live_state:  # Stream went live
                await self.send_notification(config)
                await self.logging_service.log_info(
                    f"Stream went live\n"
                    f"Platform: {config['platform']}\n"
                    f"URL: {config['profile_url']}"
                )
            else:  # Stream ended
                await self.logging_service.log_info(
                    f"Stream ended\n"
                    f"Platform: {config['platform']}\n"
                    f"URL: {config['profile_url']}"
                )

            # Update stream status
            if config['profile_url'] in self.stream_statuses:
                self.stream_statuses[config['profile_url']].is_live = current_live_state

            # Update configuration
            config['is_live'] = current_live_state
            self.config_service.save_stream_state(config['profile_url'], current_live_state)

        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error handling stream state change for {config['profile_url']}"
            )
            raise

    async def send_notification(self, config):
        """Send notification about stream going live"""
        try:
            channel = self.client.get_channel(config['channel_id'])
            if not channel:
                await self.handle_missing_channel(config)
                return

            # Create embed for notification
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

            # Add timestamp
            embed.timestamp = datetime.now()

            # Send notification with role mention and embed
            message = f"<@&{config['role_id']}>"
            await channel.send(message, embed=embed)
            
            await self.logging_service.log_info(
                f"Sent notification\n"
                f"Channel: {channel.name}\n"
                f"Stream: {config['profile_url']}"
            )

        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error sending notification for {config['profile_url']}"
            )
            raise

    async def get_service_status(self) -> Dict[str, Any]:
        """Get detailed service status information"""
        return {
            "service": {
                "status": self.service_status.value,
                "uptime": str(datetime.now() - self.start_time) if self.start_time else "Not started",
                "last_error": str(self.last_error) if self.last_error else None
            },
            "streams": {
                url: {
                    "status": status.status.value,
                    "last_check": status.last_check.isoformat() if status.last_check else None,
                    "last_successful_check": status.last_successful_check.isoformat() if status.last_successful_check else None,
                    "is_live": status.is_live,
                    "error_count": status.error_count,
                    "success_count": status.success_count,
                    "consecutive_errors": status.consecutive_errors,
                    "last_error": status.last_error
                } for url, status in self.stream_statuses.items()
            },
            "configurations": self.config_service.get_all_configurations()
        }

    async def stop_checking(self):
        """Safely stops all checking tasks"""
        self.is_running = False
        self.service_status = ServiceStatus.STOPPED
        
        for url, task_info in self.checking_tasks.items():
            try:
                if not task_info['task'].done():
                    task_info['task'].cancel()
                    await task_info['task']  # Wait for task to be cancelled
                if url in self.stream_statuses:
                    self.stream_statuses[url].status = ServiceStatus.STOPPED
            except asyncio.CancelledError:
                pass  # Expected when cancelling tasks
            except Exception as e:
                await self.logging_service.log_error(e, f"Error while stopping task for {url}")
        
        self.checking_tasks.clear()
        await self.logging_service.log_info("All checking tasks have been stopped")

    async def reload_configuration(self):
        """Reload service configuration and restart checking tasks"""
        print("Reloading notification service configuration...")
        try:
            # Stop existing tasks
            await self.stop_checking()
            
            # Clear existing tasks and statuses
            self.checking_tasks.clear()
            self.stream_statuses.clear()
            
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
            
            if config['profile_url'] not in self.checking_tasks:
                # Create new checking task
                task = asyncio.create_task(self.check_stream_loop(config))
                self.checking_tasks[config['profile_url']] = {
                    'task': task,
                    'last_check': datetime.now(),
                    'status': 'running'
                }
                
                # Initialize stream status
                self.stream_statuses[config['profile_url']] = StreamCheckStatus()
                self.stream_statuses[config['profile_url']].status = ServiceStatus.RUNNING
                
                await self.logging_service.log_info(
                    f"Started checking for new configuration: {config['profile_url']}"
                )
            else:
                await self.logging_service.log_info(
                    f"Configuration already exists for {config['profile_url']}"
                )
        
        except Exception as e:
            await self.logging_service.log_error(
                e, 
                f"Error adding new configuration for {config['profile_url']}"
            )
            raise

    async def send_notification(self, config):
        """Sends notification with error handling"""
        try:
            channel = self.client.get_channel(config['channel_id'])
            if channel:
                message = f"<@&{config['role_id']}> {config['message']}\n{config['profile_url']}"
                await channel.send(message)
                await self.logging_service.log_info(
                    f"Sent notification\n"
                    f"Channel: {channel.name}\n"
                    f"Stream: {config['profile_url']}"
                )
        except Exception as e:
            await self.logging_service.log_error(
                e,
                f"Error while sending notification\n"
                f"Channel: {config.get('channel_id')}\n"
                f"Stream: {config['profile_url']}"
            ) 