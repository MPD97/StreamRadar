from typing import Dict, Any, List
import asyncio
import discord
from interfaces.repository_interface import IStreamRepository
from services.logging_service import LoggingService
from services.config_manager import ConfigManager
from utils.embed_builder import EmbedBuilder
from platforms.twitch_platform import TwitchPlatform
from platforms.tiktok_platform import TikTokPlatform

class NotificationManager:
    """Manages stream notifications and status checking"""
    
    def __init__(self, bot: discord.Client, repository: IStreamRepository, 
                 logging_service: LoggingService, config_service: ConfigManager,
                 check_interval: int = 60):
        self.bot = bot
        self.repository = repository
        self.logging_service = logging_service
        self.config_service = config_service
        self.check_interval = check_interval
        self.active_checks = {}
        self._is_running = False
        
        # Initialize platforms
        self.platforms = {
            'twitch': TwitchPlatform(config_service),
            'tiktok': TikTokPlatform(config_service)
        }

    async def start_all_monitoring(self) -> None:
        """Start monitoring all active stream configurations"""
        if self._is_running:
            return

        self._is_running = True
        try:
            configs = await self.repository.get_all()
            if not configs:
                await self.logging_service.log_info("No active stream configurations found")
                return

            await self.logging_service.log_info(f"Starting monitoring for {len(configs)} streams")
            for config in configs:
                if config.get('is_active', True):  # Only monitor active configurations
                    await self.start_monitoring(config)
                    
        except Exception as e:
            await self.logging_service.log_error(e, "Error starting stream monitoring")
            self._is_running = False

    async def stop_all_monitoring(self) -> None:
        """Stop all active monitoring tasks"""
        if not self._is_running:
            return

        self._is_running = False
        try:
            configs = await self.repository.get_all()
            if configs:
                await self.logging_service.log_info(f"Stopping monitoring for {len(configs)} streams")
                for config in configs:
                    await self.stop_monitoring(config)
        except Exception as e:
            await self.logging_service.log_error(e, "Error stopping stream monitoring")

    async def start_monitoring(self, config: Dict[str, Any]) -> None:
        """Start monitoring a stream"""
        key = self._get_stream_key(config)
        if key not in self.active_checks:
            self.active_checks[key] = True
            asyncio.create_task(self._check_stream_loop(config))
            await self.logging_service.log_info(f"Started monitoring: {config['profile_url']}")

    async def stop_monitoring(self, config: Dict[str, Any]) -> None:
        """Stop monitoring a stream"""
        key = self._get_stream_key(config)
        if key in self.active_checks:
            self.active_checks[key] = False
            await self.logging_service.log_info(f"Stopped monitoring: {config['profile_url']}")

    async def send_notification(self, config: Dict[str, Any], stream_info: Dict[str, Any]) -> None:
        """Send stream notification"""
        try:
            channel = self.bot.get_channel(config['channel_id'])
            if not channel:
                await self.logging_service.log_error(f"Channel not found: {config['channel_id']}")
                return

            embed = EmbedBuilder.create_stream_notification(config, stream_info)
            await channel.send(content=config['message'], embed=embed)
            
            # Update stream status in database
            await self.repository.update_status(
                guild_id=config['guild_id'],
                platform=config['platform'],
                username=config['username'],
                is_live=True
            )

        except Exception as e:
            await self.logging_service.log_error(f"Error sending notification: {str(e)}")

    async def check_stream(self, config: Dict[str, Any]) -> None:
        """Check stream status and send notification if needed"""
        try:
            platform = self.platforms.get(config['platform'])
            if not platform:
                await self.logging_service.log_error(f"Unknown platform: {config['platform']}")
                return

            is_live, stream_info = await platform.check_stream(config['username'])
            
            # Get current status from database
            stored_config = await self.repository.get(
                config['guild_id'],
                config['platform'],
                config['username']
            )
            
            was_live = stored_config.get('is_live', False) if stored_config else False

            if is_live and not was_live:
                await self.logging_service.log_info(f"Stream went live: {config['profile_url']}")
                await self.send_notification(config, stream_info)
            elif not is_live and was_live:
                await self.repository.update_status(
                    guild_id=config['guild_id'],
                    platform=config['platform'],
                    username=config['username'],
                    is_live=False
                )

        except Exception as e:
            await self.logging_service.log_error(f"Error checking stream: {str(e)}")

    async def _check_stream_loop(self, config: Dict[str, Any]) -> None:
        
        key = self._get_stream_key(config)
        
        while self.active_checks.get(key, False):
            try:
                
                # Get current status from database
                stored_config = await self.repository.get(
                    config['guild_id'],
                    config['platform'],
                    config['username']
                )
                was_live = stored_config.get('is_live', False) if stored_config else False
                
                status_result = await self._check_stream_status(config)
                current_status = status_result.get('is_live', False)

                if current_status and not was_live:
                    await self.logging_service.log_info(
                        f"Stream went live: {config['profile_url']}"
                    )
                    await self.send_notification(config, status_result)
                
                await self.repository.update_status(
                    config['guild_id'],
                    config['platform'],
                    config['username'],
                    current_status
                )

            except Exception as e:
                await self.logging_service.log_error(e, f"Error checking stream: {config['profile_url']}")

            await asyncio.sleep(self.check_interval)

    async def _check_stream_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check current stream status"""
        platform = self.platforms.get(config['platform'].lower())
        if not platform:
            raise ValueError(f"Unsupported platform: {config['platform']}")

        status = await platform.is_stream_live(config['profile_url'])
        
        await self.logging_service.log_debug(
            f"Stream check result for {config['profile_url']}: {'Live' if status else 'Offline'}"
        )
        
        return status

    def _get_stream_key(self, config: Dict[str, Any]) -> str:
        """Generate unique key for stream"""
        return f"{config['guild_id']}:{config['platform']}:{config['username']}"

    def _format_notification_message(self, config: Dict[str, Any]) -> str:
        """Format notification message"""
        role_mention = f"<@&{config['role_id']}>" if config['role_id'] else ""
        return f"{role_mention} {config['message']}" 