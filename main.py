import os
import discord
from discord.ext import commands
import asyncio
import logging
from typing import Dict, Any
from services.database_service import SQLiteDatabase
from services.config_manager import ConfigManager
from services.stream_service import StreamService
from services.notification_manager import NotificationManager
from services.logging_service import LoggingService
from services.error_handler import ErrorHandler
from commands.add_config_command import setup_add_config_command
from commands.delete_config_command import setup_delete_config_command
from commands.status_command import setup_status_command

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)

logger = logging.getLogger(__name__)

class NotificationBot(commands.Bot):
    def __init__(self, config: Dict[str, Any]):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(
            command_prefix=config['prefix'],
            intents=intents,
            help_command=None
        )

        self.config = config
        self._setup_services()

    def _setup_services(self) -> None:
        """Initialize bot services"""
        try:
            # Initialize logging first
            self.logging_service = LoggingService(
                log_level=self.config.get('log_level', 'INFO'),
                log_channel_id=self.config.get('log_channel_id')
            )
            self.logging_service.set_bot(self)
            
            # Initialize config and error handler
            self.config_manager = ConfigManager()
            self.error_handler = ErrorHandler(self.logging_service)
            
            # Initialize database
            self.db_service = SQLiteDatabase('database.sqlite')
            
            # Initialize stream service with logging
            self.stream_service = StreamService(
                self.db_service,
                self.logging_service,
                self.config_manager
            )
            
            # Initialize notification manager last
            self.notification_manager = NotificationManager(
                bot=self,
                repository=self.db_service,
                logging_service=self.logging_service,
                config_service=self.config_manager,
                check_interval=self.config.get('check_interval', 60)
            )
            
            logger.info("Services initialized successfully")

        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            raise

    async def setup_hook(self) -> None:
        """Setup bot hooks and start services"""
        try:
            # Initialize database
            await self.db_service.initialize()
            logger.info("Database initialized successfully")
            
            # Setup commands
            setup_add_config_command(self)
            setup_delete_config_command(self)
            setup_status_command(self)
            logger.info("Commands setup completed")

            # Start notification service
            await self.notification_manager.start_all_monitoring()
            logger.info("Notification service started")
            
            logger.info("Bot setup completed successfully")

        except Exception as e:
            logger.error(f"Error in setup hook: {e}")
            raise

    async def close(self) -> None:
        """Cleanup before shutdown"""
        try:
            # Stop notification service
            if hasattr(self, 'notification_manager'):
                await self.notification_manager.stop_all_monitoring()
                logger.info("Notification service stopped")

            # Close database connection
            if hasattr(self, 'db_service'):
                await self.db_service.close()
                logger.info("Database connection closed")

            await super().close()
            logger.info("Bot shutdown completed successfully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
            raise

async def run_bot_async():
    """Run bot asynchronously"""
    try:
        config = {
            'prefix': os.getenv('BOT_PREFIX', '!'),
            'token': os.getenv('DISCORD_TOKEN'),
            'check_interval': int(os.getenv('CHECK_INTERVAL', '60')),
            'log_level': os.getenv('LOG_LEVEL', 'INFO'),
            'log_channel_id': int(os.getenv('LOG_CHANNEL_ID', '0')) or None
        }

        if not config['token']:
            raise ValueError("Discord token not found in environment variables")

        bot = NotificationBot(config)
        async with bot:
            await bot.start(config['token'])

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise

def run_bot():
    """Run bot"""
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    run_bot() 