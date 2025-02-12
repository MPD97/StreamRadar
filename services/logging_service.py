import logging
import discord
from typing import Optional, Union
from datetime import datetime
from .config_service import LogLevel

logger = logging.getLogger(__name__)

class LoggingService:
    """Service for handling logging and error reporting"""

    def __init__(self, log_level: str = 'INFO', log_channel_id: Optional[int] = None):
        """Initialize logging service"""
        self.bot = None
        self.log_channel_id = log_channel_id
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.logger = logging.getLogger(__name__)

    def set_bot(self, bot: discord.Client) -> None:
        """Set bot instance for Discord channel logging"""
        self.bot = bot

    async def _send_log(self, guild_id: Optional[int], level: str, message: str, error: Exception = None):
        """Send log message to configured channel"""
        try:
            if guild_id:
                config = await self.config_service.get_logging_config(guild_id)
                if config and config.get('channel_id'):
                    channel = self.bot.get_channel(config['channel_id'])
                    if channel:
                        embed = discord.Embed(
                            title=f"Bot Log - {level}",
                            description=message,
                            color=self._get_level_color(level),
                            timestamp=datetime.now()
                        )
                        
                        if error:
                            embed.add_field(
                                name="Error Details",
                                value=f"```{str(error)}```",
                                inline=False
                            )
                            
                            # Add traceback if available
                            import traceback
                            tb = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
                            if len(tb) > 1000:
                                tb = tb[:997] + "..."
                            embed.add_field(
                                name="Traceback",
                                value=f"```python\n{tb}```",
                                inline=False
                            )
                        
                        await channel.send(embed=embed)

            # Always print to console
            log_message = f"[{datetime.now().isoformat()}] [{level}] {message}"
            if error:
                log_message += f"\nError: {str(error)}"
            print(log_message)

        except Exception as e:
            print(f"Error in logging service: {str(e)}")
            if error:
                print(f"Original error: {str(error)}")

    def _get_level_color(self, level: str) -> discord.Color:
        """Get color for log level"""
        return {
            LogLevel.DEBUG: discord.Color.light_grey(),
            LogLevel.INFO: discord.Color.blue(),
            LogLevel.WARNING: discord.Color.yellow(),
            LogLevel.ERROR: discord.Color.red()
        }.get(level, discord.Color.default())

    async def log_debug(self, message: str) -> None:
        """Log debug message"""
        self.logger.debug(message)
        await self._log_to_discord("DEBUG", message)

    async def log_info(self, message: str) -> None:
        """Log info message"""
        self.logger.info(message)
        await self._log_to_discord("INFO", message)

    async def log_warning(self, message: str) -> None:
        """Log warning message"""
        self.logger.warning(message)
        await self._log_to_discord("WARNING", message)

    async def log_error(self, error: Union[Exception, str], context: str = "") -> None:
        """Log error message with optional context"""
        error_message = f"{context}: {str(error)}" if context else str(error)
        self.logger.error(error_message)
        await self._log_to_discord("ERROR", error_message)

    async def log_critical(self, error: Exception, context: str = ""):
        """Log critical error message with context"""
        message = context if context else "A critical error occurred"
        await self._send_log(None, LogLevel.CRITICAL, message, error)

    async def _log_to_discord(self, level: str, message: str) -> None:
        """Log message to Discord channel if configured"""
        if not self.bot or not self.log_channel_id:
            return

        try:
            channel = self.bot.get_channel(self.log_channel_id)
            if channel:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                await channel.send(f"```\n{timestamp} [{level}] {message}\n```")
        except Exception as e:
            self.logger.error(f"Failed to log to Discord: {e}") 