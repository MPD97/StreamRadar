import discord
from datetime import datetime
from .config_service import LogLevel

class LoggingService:
    def __init__(self, client, config_service):
        self.client = client
        self.config_service = config_service

    async def _log(self, level: LogLevel, message: str, error: Exception = None):
        """Internal method for logging messages"""
        try:
            config = self.config_service.get_logging_config()
            if not config or not config.get('channel_id'):
                print(f"No logging channel configured. Message: {message}")
                return

            # Check if we should log this level
            if level.value < LogLevel[config.get('level', 'INFO')].value:
                return

            channel = self.client.get_channel(config['channel_id'])
            if not channel:
                print(f"Could not find logging channel. ID: {config['channel_id']}")
                return

            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_message = f"[{timestamp}] [{level.name:8}] {message}"
            
            if error:
                log_message += f"\nError: {str(error)}"
                if hasattr(error, '__traceback__'):
                    import traceback
                    log_message += f"\nStacktrace:\n{traceback.format_exc()}"

            # Split long messages
            max_length = 1900  # Discord message limit is 2000
            messages = [log_message[i:i+max_length] for i in range(0, len(log_message), max_length)]
            
            for msg in messages:
                await channel.send(f"```\n{msg}\n```")

        except Exception as e:
            print(f"Error in logging service: {str(e)}")
            print(f"Original message: {message}")
            if error:
                print(f"Original error: {str(error)}")

    async def log_debug(self, message: str):
        """Log debug message"""
        await self._log(LogLevel.DEBUG, message)

    async def log_info(self, message: str):
        """Log info message"""
        await self._log(LogLevel.INFO, message)

    async def log_warning(self, message: str):
        """Log warning message"""
        await self._log(LogLevel.WARNING, message)

    async def log_error(self, error: Exception, context: str = ""):
        """Log error message with context"""
        message = context if context else "An error occurred"
        await self._log(LogLevel.ERROR, message, error)

    async def log_critical(self, error: Exception, context: str = ""):
        """Log critical error message with context"""
        message = context if context else "A critical error occurred"
        await self._log(LogLevel.CRITICAL, message, error) 