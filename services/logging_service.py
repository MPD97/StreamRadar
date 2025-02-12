import logging
import discord
from datetime import datetime
from typing import Optional
from .config_service import LogLevel

logger = logging.getLogger(__name__)

class LoggingService:
    def __init__(self, bot, config_service):
        self.bot = bot
        self.config_service = config_service
        self.default_log_level = LogLevel.INFO

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

    async def log_debug(self, message: str, guild_id: Optional[int] = None):
        """Log debug message"""
        await self._send_log(guild_id, LogLevel.DEBUG, message)

    async def log_info(self, message: str, guild_id: Optional[int] = None):
        """Log info message"""
        try:
            logger.info(message)
            
            if guild_id:
                # Możesz dodać tutaj dodatkową logikę logowania do bazy danych
                pass
                
        except Exception as e:
            logger.error(f"Error in logging service: {str(e)}\nMessage: {message}")

    async def log_warning(self, message: str, guild_id: Optional[int] = None):
        """Log warning message"""
        try:
            logger.warning(message)
            
            if guild_id:
                # Możesz dodać tutaj dodatkową logikę logowania do bazy danych
                pass
                
        except Exception as e:
            logger.error(f"Error in logging service: {str(e)}\nMessage: {message}")

    async def log_error(self, error: Exception, message: str, guild_id: Optional[int] = None):
        """Log error message"""
        try:
            error_message = f"{message}\nError: {str(error)}"
            logger.error(error_message)
            
            if guild_id:
                # Możesz dodać tutaj dodatkową logikę logowania do bazy danych
                pass
                
        except Exception as e:
            logger.error(f"Error in logging service: {str(e)}\nOriginal error: {str(error)}")

    async def log_critical(self, error: Exception, context: str = ""):
        """Log critical error message with context"""
        message = context if context else "A critical error occurred"
        await self._send_log(None, LogLevel.CRITICAL, message, error) 