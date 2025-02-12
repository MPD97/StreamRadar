from typing import Dict, Any, List
import asyncio
import discord
from interfaces.repository_interface import IStreamRepository
from services.logging_service import LoggingService
from utils.embed_builder import EmbedBuilder

class NotificationManager:
    """Manages stream notifications and status checking"""
    
    def __init__(self, bot: discord.Client, repository: IStreamRepository, 
                 logging_service: LoggingService, check_interval: int = 60):
        self.bot = bot
        self.repository = repository
        self.logging_service = logging_service
        self.check_interval = check_interval
        self.active_checks: Dict[str, bool] = {}
        self.embed_builder = EmbedBuilder()

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
        """Send stream notification to Discord channel"""
        try:
            channel = self.bot.get_channel(config['channel_id'])
            if not channel:
                await self.logging_service.log_error(
                    Exception(f"Channel not found: {config['channel_id']}"),
                    "Notification error"
                )
                return

            embed = await self.embed_builder.create_stream_notification(config, stream_info)
            message = self._format_notification_message(config)
            await channel.send(content=message, embed=embed)

        except Exception as e:
            await self.logging_service.log_error(e, "Error sending notification")

    async def _check_stream_loop(self, config: Dict[str, Any]) -> None:
        """Continuous stream status checking loop"""
        key = self._get_stream_key(config)
        last_status = False

        while self.active_checks.get(key, False):
            try:
                current_status = await self._check_stream_status(config)
                
                if current_status and not last_status:
                    await self.send_notification(config, current_status)
                
                last_status = bool(current_status)
                await self.repository.update_status(
                    config['guild_id'],
                    config['platform'],
                    config['username'],
                    last_status
                )

            except Exception as e:
                await self.logging_service.log_error(e, f"Error checking stream: {config['profile_url']}")
                last_status = False

            await asyncio.sleep(self.check_interval)

    async def _check_stream_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Check current stream status"""
        platform = self.get_platform(config['platform'])
        if not platform:
            raise ValueError(f"Unsupported platform: {config['platform']}")

        return await platform.check_stream_status(config['username'])

    def _get_stream_key(self, config: Dict[str, Any]) -> str:
        """Generate unique key for stream"""
        return f"{config['guild_id']}:{config['platform']}:{config['username']}"

    def _format_notification_message(self, config: Dict[str, Any]) -> str:
        """Format notification message"""
        role_mention = f"<@&{config['role_id']}>" if config['role_id'] else ""
        return f"{role_mention} {config['message']}" 