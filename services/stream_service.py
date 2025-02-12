from typing import Dict, List, Any, Optional
import discord
from interfaces.service_interface import IStreamService
from interfaces.repository_interface import IStreamRepository
from services.logging_service import LoggingService
from services.config_manager import ConfigManager
from utils.validators import Validators

class StreamService(IStreamService):
    """Service for managing stream configurations"""

    def __init__(self, repository: IStreamRepository, 
                 logging_service: LoggingService,
                 config_manager: ConfigManager):
        self.repository = repository
        self.logging_service = logging_service
        self.config_manager = config_manager
        self.validators = Validators()

    async def add_stream(self, ctx: Any, platform: str, profile_url: str,
                        role: discord.Role, message: str) -> bool:
        """Add new stream to monitoring"""
        try:
            if not await self._validate_stream_input(platform, profile_url):
                return False

            config = self._create_stream_config(ctx, platform, profile_url, role, message)
            await self.repository.save(config)
            await self.notification_service.add_configuration(config)
            return True

        except Exception as e:
            await self.logging_service.log_error(e, "Error adding stream")
            return False

    async def remove_stream(self, ctx: Any, profile_url: str) -> bool:
        """Remove stream from monitoring"""
        try:
            config = await self.repository.get(ctx.guild.id, profile_url)
            if not config:
                return False
            
            print(f"[BUG7] config: {config}")

            await self.repository.delete(ctx.guild.id, profile_url)
            await self.notification_service.remove_configuration(
                ctx.guild.id,
                config['username'],
                config['platform']
            )
            return True

        except Exception as e:
            await self.logging_service.log_error(e, "Error removing stream")
            return False

    async def get_streams(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all streams for guild"""
        try:
            configs = await self.repository.get_all()
            return [c for c in configs if c['guild_id'] == guild_id]
        except Exception as e:
            await self.logging_service.log_error(e, "Error getting streams")
            return []

    async def get_stream_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get stream status"""
        try:
            return await self.notification_service.get_stream_status(config)
        except Exception as e:
            await self.logging_service.log_error(e, "Error getting stream status")
            return {'is_live': False, 'error': str(e)}

    async def _validate_stream_input(self, platform: str, profile_url: str) -> bool:
        """Validate stream input data"""
        if not Validators.validate_url(profile_url):
            return False

        platform_service = self.notification_service.platforms.get(platform.lower())
        if not platform_service:
            return False

        return True

    def _create_stream_config(self, ctx: Any, platform: str, profile_url: str,
                            role: discord.Role, message: str) -> Dict[str, Any]:
        """Create stream configuration"""
        platform_service = self.notification_service.platforms[platform.lower()]
        return {
            'guild_id': ctx.guild.id,
            'platform': platform.lower(),
            'username': platform_service.get_username_from_url(profile_url),
            'profile_url': profile_url,
            'channel_id': ctx.channel.id,
            'channel_name': ctx.channel.name,
            'role_id': role.id,
            'role_name': role.name,
            'message': message
        } 