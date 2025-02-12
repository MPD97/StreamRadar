import os
import discord
from discord import app_commands
import asyncio
import logging
from typing import Optional

from services.database_service import DatabaseService
from services.config_service import ConfigurationService
from services.notification_service import NotificationService
from services.logging_service import LoggingService
from commands import CommandManager

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

class NotificationBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)
        self._ready = asyncio.Event()
        self._setup_complete = False

    async def setup_hook(self):
        """Initialize bot services and commands"""
        try:
            logger.info("Setting up bot hooks...")
            
            logger.info("Initializing services...")
            self.db_service = DatabaseService()
            self.config_service = ConfigurationService(self.db_service)
            self.logging_service = LoggingService(self, self.config_service)
            self.notification_service = NotificationService(
                self,
                self.config_service,
                self.logging_service
            )
            logger.info("Services initialized successfully")

            logger.info("Initializing database...")
            await self.db_service.initialize()
            await self.config_service.initialize()
            logger.info("Database initialized")

            logger.info("Initializing platforms...")
            # Tu możesz dodać inicjalizację platform
            logger.info("Platforms initialized")

            logger.info("Setting up commands...")
            self.command_manager = CommandManager(self)
            self.command_manager.setup()
            await self.tree.sync()
            logger.info("Commands setup complete")

            self._setup_complete = True
            logger.info("Bot setup complete")

        except Exception as e:
            logger.error(f"Error in setup_hook: {e}", exc_info=True)
            raise

    async def on_ready(self):
        """Handle bot ready event"""
        try:
            if not self._setup_complete:
                logger.warning("Bot ready but setup not complete!")
                return

            logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
            logger.info(f'Connected to {len(self.guilds)} guilds')
            
            logger.info("Starting notification service...")
            await self.notification_service.start_checking()
            logger.info("Notification service started")
            
            self._ready.set()
            logger.info("Bot is fully ready")

        except Exception as e:
            logger.error(f"Error in on_ready: {e}", exc_info=True)
            self._ready.set()

async def run_bot_async():
    try:
        logger.info("Starting bot...")
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            logger.error("DISCORD_TOKEN not found in environment variables")
            return

        async with NotificationBot() as bot:
            await bot.start(token)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete")

def run_bot():
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    run_bot() 