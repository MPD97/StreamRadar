import os
import asyncio
import discord
from discord import app_commands
import asyncio
from services.config_service import ConfigurationService, LogLevel
from services.notification_service import NotificationService
from services.logging_service import LoggingService
import logging
from services.database_service import DatabaseService
from datetime import datetime
from discord.ui import View, Button

# Konfiguracja podstawowego logowania
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logi do konsoli
        logging.FileHandler('bot.log')  # Logi do pliku
    ]
)

logger = logging.getLogger(__name__)

# Dodajemy klasę przycisku do usuwania konfiguracji
class DeleteConfigButton(Button):
    def __init__(self, config_id, bot, guild_id, profile_url):
        # Wyciągnij username ze streamu
        username = profile_url.split('/')[-1] if profile_url else 'unknown'
        platform = 'Twitch'  # Na razie tylko Twitch, w przyszłości można rozszerzyć
        
        # Ustaw label z informacją o platformie i username
        super().__init__(
            label=f"Delete {platform}: {username}",
            style=discord.ButtonStyle.danger,
            custom_id=f"delete_config_{config_id}"
        )
        
        self.config_id = config_id
        self.bot = bot
        self.guild_id = guild_id
        self.profile_url = profile_url

    async def callback(self, interaction: discord.Interaction):
        try:
            # Sprawdź uprawnienia użytkownika
            if not interaction.user.guild_permissions.manage_guild:
                await interaction.response.send_message(
                    "Nie masz uprawnień do usuwania konfiguracji.", 
                    ephemeral=True
                )
                return

            # Usuń konfigurację
            deleted = await self.bot.config_service.delete_configuration(
                self.guild_id, 
                self.profile_url
            )

            username = self.profile_url.split('/')[-1]

            if deleted:
                # Usuń konfigurację z usługi powiadomień
                await self.bot.notification_service.remove_configuration(
                    self.guild_id, 
                    self.profile_url
                )
                await interaction.response.send_message(
                    f"Konfiguracja dla streamera `{username}` została usunięta.", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Nie udało się usunąć konfiguracji dla streamera `{username}`.", 
                    ephemeral=True
                )

        except Exception as e:
            await self.bot.logging_service.log_error(
                e, 
                f"Error deleting configuration {self.profile_url}", 
                self.guild_id
            )
            await interaction.response.send_message(
                "Wystąpił błąd podczas usuwania konfiguracji.", 
                ephemeral=True
            )

# Dodajemy klasę widoku zawierającą przyciski do usuwania
class StatusView(View):
    def __init__(self, configs, bot):
        super().__init__(timeout=None)  # Nie wygasa automatycznie
        for config in configs:
            button = DeleteConfigButton(
                config_id=config['id'], 
                bot=bot, 
                guild_id=config['guild_id'], 
                profile_url=config['profile_url']
            )
            self.add_item(button)

class NotificationBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.all()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self._commands_setup = False
        self._ready = asyncio.Event()
        
        try:
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
        except Exception as e:
            logger.error(f"Error initializing services: {e}", exc_info=True)
            raise

    async def setup_hook(self):
        """Setup bot hooks and initialize services"""
        try:
            logger.info("Setting up bot hooks...")
            
            logger.info("Initializing database...")
            await self.db_service.initialize()
            logger.info("Database initialized")
            
            logger.info("Initializing config service...")
            await self.config_service.initialize()
            logger.info("Config service initialized")
            
            logger.info("Initializing platforms...")
            for platform_name, platform in self.notification_service.platforms.items():
                logger.info(f"Initializing platform: {platform_name}")
                if hasattr(platform, 'initialize'):
                    await platform.initialize()
            logger.info("Platforms initialized")
            
            logger.info("Setting up commands...")
            self.setup_commands()
            logger.info("Commands set up")
            
            logger.info("Syncing command tree...")
            await self.tree.sync()
            logger.info("Command tree synced")
            
            logger.info("Bot setup completed successfully")
        except Exception as e:
            logger.error(f"Error in setup_hook: {e}", exc_info=True)
            raise

    async def on_guild_join(self, guild: discord.Guild):
        """Handle bot joining a new server"""
        await self.db_service.add_or_update_server(guild.id, guild.name)
        await self.logging_service.log_info(f"Joined new guild: {guild.name} ({guild.id})")

    async def on_guild_remove(self, guild: discord.Guild):
        """Handle bot leaving/being removed from a server"""
        # The database cascade will handle cleaning up configurations
        await self.logging_service.log_info(f"Left guild: {guild.name} ({guild.id})")

    def setup_commands(self):
        """Setup bot commands"""
        if self._commands_setup:
            return

        @self.tree.command(
            name="add-configuration",
            description="Add a new stream notification configuration"
        )
        @app_commands.describe(
            platform="Stream platform (twitch)",
            profile_url="Stream profile URL",
            channel="Channel for notifications",
            role="Role to mention",
            message="Custom notification message"
        )
        async def add_configuration(
            interaction: discord.Interaction,
            platform: str,
            profile_url: str,
            channel: discord.TextChannel,
            role: discord.Role,
            message: str = None
        ):
            try:
                await interaction.response.defer(ephemeral=True)
                
                if not interaction.guild_id:
                    await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                    return

                # Validate platform
                if platform.lower() not in ['twitch']:
                    await interaction.followup.send("Unsupported platform. Currently only Twitch is supported.", ephemeral=True)
                    return

                # Create configuration
                config = {
                    'guild_id': interaction.guild_id,
                    'platform': platform.lower(),
                    'profile_url': profile_url,
                    'channel_id': channel.id,
                    'channel_name': channel.name,
                    'role_id': role.id,
                    'role_name': role.name,
                    'message': message or f"{role.mention} Stream is live!"
                }

                await self.config_service.save_configuration(config)
                await self.notification_service.add_configuration(config)
                
                await interaction.followup.send(
                    f"Stream notification configuration added:\n"
                    f"Platform: {platform}\n"
                    f"Profile: {profile_url}\n"
                    f"Channel: {channel.mention}\n"
                    f"Role: {role.mention}",
                    ephemeral=True
                )

            except Exception as e:
                await self.logging_service.log_error(e, "Error adding configuration", interaction.guild_id)
                await interaction.followup.send("An error occurred while adding the configuration.", ephemeral=True)

        @self.tree.command(
            name="delete-configuration",
            description="Delete a stream notification configuration"
        )
        @app_commands.describe(
            profile_url="Stream profile URL to delete configuration for"
        )
        async def delete_configuration(
            interaction: discord.Interaction,
            profile_url: str
        ):
            try:
                await interaction.response.defer(ephemeral=True)
                
                if not interaction.guild_id:
                    await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                    return

                # Check if configuration exists
                config = await self.config_service.get_configuration(interaction.guild_id, profile_url)
                if not config:
                    await interaction.followup.send(
                        f"No configuration found for `{profile_url}` in this server.",
                        ephemeral=True
                    )
                    return

                # Usuń konfigurację
                deleted = await self.config_service.delete_configuration(
                    interaction.guild_id,
                    profile_url
                )

                if deleted:
                    await self.notification_service.remove_configuration(interaction.guild_id, profile_url)
                    await interaction.followup.send(
                        f"Configuration for `{profile_url}` has been deleted.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(
                        f"Failed to delete configuration for `{profile_url}`.",
                        ephemeral=True
                    )

            except Exception as e:
                await self.logging_service.log_error(e, f"Error deleting configuration: {str(e)}", interaction.guild_id)
                await interaction.followup.send("An error occurred while deleting the configuration.", ephemeral=True)

        @self.tree.command(
            name="list-configurations",
            description="List all stream notification configurations for this server"
        )
        async def list_configurations(interaction: discord.Interaction):
            try:
                await interaction.response.defer(ephemeral=True)
                
                if not interaction.guild_id:
                    await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                    return

                configs = await self.config_service.get_server_configurations(interaction.guild_id)
                
                if not configs:
                    await interaction.followup.send("No configurations found for this server.", ephemeral=True)
                    return

                embed = discord.Embed(
                    title="Stream Notification Configurations",
                    color=discord.Color.blue()
                )

                for config in configs:
                    status = "🟢 Active" if config['is_active'] else "🔴 Inactive"
                    if config.get('error_message'):
                        status += f"\n⚠️ Error: {config['error_message']}"

                    embed.add_field(
                        name=f"{config['platform'].capitalize()} - {config['profile_url']}",
                        value=f"Status: {status}\n"
                              f"Channel: <#{config['channel_id']}>\n"
                              f"Role: <@&{config['role_id']}>",
                        inline=False
                    )

                await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                await self.logging_service.log_error(e, "Error listing configurations", interaction.guild_id)
                await interaction.followup.send("An error occurred while listing configurations.", ephemeral=True)

        @self.tree.command(
            name="status",
            description="Show status of stream notifications for this server"
        )
        async def status(interaction: discord.Interaction):
            try:
                await interaction.response.defer(ephemeral=True)
                
                if not interaction.guild_id:
                    await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                    return

                guild = interaction.guild
                bot_member = guild.me

                if not bot_member:
                    await interaction.followup.send("Bot is not a member of this guild.", ephemeral=True)
                    return

                # Sprawdź uprawnienia w kanale, w którym została użyta komenda
                channel_permissions = interaction.channel.permissions_for(bot_member)

                # Określ wymagane uprawnienia
                required_permissions = {
                    'send_messages': 'Send Messages',
                    'embed_links': 'Embed Links',
                    'manage_messages': 'Manage Messages',
                    'view_channel': 'View Channel'
                }

                permission_status = []
                for perm, description in required_permissions.items():
                    has_perm = getattr(channel_permissions, perm, False)
                    status = "✅" if has_perm else "❌"
                    permission_status.append(f"{description}: {status}")

                permission_info = "\n".join(permission_status)

                configs = await self.config_service.get_server_configurations(interaction.guild_id)
                
                # Zawsze tworzymy embed z informacjami o uprawnieniach
                embed = discord.Embed(
                    title="Stream Notifications Status",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )

                if not configs:
                    embed.description = "No stream notifications configured for this server."
                else:
                    embed.description = "Current status of stream notifications"
                    for config in configs:
                        status_emoji = "🟢" if config['is_active'] else "🔴"
                        live_status = "🎥 Live" if config.get('is_live') else "⭕ Offline"
                        
                        last_check = config.get('last_check')
                        if last_check:
                            if isinstance(last_check, str):
                                try:
                                    last_check = datetime.fromisoformat(last_check).strftime('%Y-%m-%d %H:%M:%S')
                                except ValueError:
                                    last_check = 'Invalid date'
                            elif isinstance(last_check, datetime):
                                last_check = last_check.strftime('%Y-%m-%d %H:%M:%S')
                            else:
                                last_check = 'Unknown'
                        else:
                            last_check = 'Never'

                        status_text = [
                            f"Status: {status_emoji} {'Active' if config['is_active'] else 'Inactive'}",
                            f"Stream: {live_status}",
                            f"Channel: <#{config['channel_id']}>",
                            f"Role: <@&{config['role_id']}>",
                            f"Last Check: {last_check}"
                        ]

                        if config.get('error_message'):
                            status_text.append(f"⚠️ Error: {config['error_message']}")

                        embed.add_field(
                            name=f"{config['platform'].capitalize()} - {config['profile_url']}",
                            value="\n".join(status_text),
                            inline=False
                        )

                # Zawsze dodajemy informacje o uprawnieniach
                embed.add_field(
                    name="Bot Permissions",
                    value=permission_info,
                    inline=False
                )

                if configs:
                    view = StatusView(configs, self)
                    await interaction.followup.send(embed=embed, view=view, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)

            except Exception as e:
                await self.logging_service.log_error(e, "Error showing status", interaction.guild_id)
                await interaction.followup.send("An error occurred while getting status.", ephemeral=True)

        self._commands_setup = True
        logger.info("Commands setup completed")

    async def on_ready(self):
        """Called when the bot is ready"""
        if self._ready.is_set():
            return
            
        try:
            logger.info(f'Logged in as {self.user.name} (ID: {self.user.id})')
            logger.info(f'Connected to {len(self.guilds)} guilds')
            
            logger.info("Starting notification service...")
            await self.notification_service.start_checking()
            logger.info("Notification service started")
            
            self._ready.set()
            logger.info("Bot is fully ready")
        except Exception as e:
            logger.error(f"Error in on_ready: {e}", exc_info=True)
            self._ready.set()  # Set the event even on error to prevent hanging

    async def start_checking_streams(self):
        while True:
            try:
                await self.notification_service.stop_checking()  # Zatrzymaj poprzednie sprawdzanie
                await self.notification_service.start_checking()
                break  # Jeśli start_checking zakończył się normalnie, przerwij pętlę
            except Exception as e:
                await self.logging_service.log_error(e, "Błąd podczas uruchamiania sprawdzania streamów")
                await asyncio.sleep(5)  # Poczekaj przed ponowną próbą

    async def on_disconnect(self):
        await self.logging_service.log_warning("Bot został rozłączony. Próba ponownego połączenia...")
        
        await self.notification_service.stop_checking()

    async def close(self):
        """Cleanup before shutdown"""
        try:
            logger.info("Starting bot shutdown...")
            
            logger.info("Cleaning up platforms...")
            for platform in self.notification_service.platforms.values():
                if hasattr(platform, 'cleanup'):
                    await platform.cleanup()
            
            logger.info("Stopping notification service...")
            if hasattr(self.notification_service, 'stop'):
                await self.notification_service.stop()
            
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
        finally:
            await super().close()

async def run_bot_async():
    """Run the bot asynchronously"""
    try:
        logger.info("Starting bot...")
        token = os.getenv('DISCORD_TOKEN')
        if not token:
            logger.error("DISCORD_TOKEN not found in environment variables")
            return

        bot = NotificationBot()
        
        async with bot:
            logger.info("Starting bot client...")
            await bot.start(token)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logger.info("Bot shutdown complete")

def run_bot():
    """Run the bot"""
    try:
        asyncio.run(run_bot_async())
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)

if __name__ == "__main__":
    run_bot() 