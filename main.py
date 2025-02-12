import os
import asyncio
import discord
from discord import app_commands
import asyncio
from services.config_service import ConfigurationService, LogLevel
from services.notification_service import NotificationService
from services.logging_service import LoggingService
import logging

# Configure Discord.py logging
logging.getLogger('discord').setLevel(logging.WARNING)
discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.WARNING)

class NotificationBot(discord.Client):
    def __init__(self):
        # Check required environment variables at startup
        required_env_vars = ['DISCORD_TOKEN', 'TWITCH_CLIENT_ID', 'TWITCH_CLIENT_SECRET']
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        
        self.tree = app_commands.CommandTree(self)
        self.config_service = ConfigurationService()
        self.logging_service = LoggingService(self, self.config_service)
        self.notification_service = NotificationService(self, self.config_service, self.logging_service)
        self._reconnect_counter = 0
        self._max_reconnects = 5
        self._commands_setup = False  # Flag to track if commands are already setup

    async def setup_hook(self):
        """Method called before on_ready"""
        if not self._commands_setup:
            self.setup_commands()
            await self.tree.sync()
            self._commands_setup = True
            print("Commands synchronized")

    def setup_commands(self):
        """Setup bot commands only once"""
        if self._commands_setup:
            return

        @self.tree.command(
            name="status",
            description="Check bot status and configurations"
        )
        async def status(interaction: discord.Interaction):
            try:
                await interaction.response.defer(ephemeral=True)
                
                status_info = await self.notification_service.get_service_status()
                
                # Create formatted status message
                embed = discord.Embed(
                    title="Bot Status",
                    color=discord.Color.blue()
                )
                
                # Service Status
                service_status = status_info["service"]
                status_color = {
                    "Running": "🟢",
                    "Stopped": "🔴",
                    "Error": "⚠️",
                    "Reconnecting": "🟡"
                }.get(service_status['status'], "⚪")
                
                embed.add_field(
                    name="Service Status",
                    value=f"{status_color} {service_status['status']}\n"
                          f"⏱️ Uptime: {service_status['uptime']}\n"
                          f"{'❌ Last Error: ' + service_status['last_error'] if service_status['last_error'] else ''}",
                    inline=False
                )
                
                # Stream Status
                for url, stream_status in status_info["streams"].items():
                    status_emoji = "🟢" if stream_status['status'] == "Running" else "🔴"
                    live_status = "🎥 Live" if stream_status['is_live'] else "⭕ Offline"
                    
                    embed.add_field(
                        name=f"Stream: {url}",
                        value=f"{status_emoji} Status: {stream_status['status']}\n"
                              f"{live_status}\n"
                              f"📊 Success Rate: {stream_status['success_count']}/{stream_status['success_count'] + stream_status['error_count']}\n"
                              f"⏱️ Last Check: {stream_status['last_check']}\n"
                              f"{'❌ Last Error: ' + stream_status['last_error'] if stream_status['last_error'] else ''}",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                
            except Exception as e:
                await self.logging_service.log_error(e, "Error getting bot status")
                await interaction.followup.send(
                    "An error occurred while getting bot status.",
                    ephemeral=True
                )

        @self.tree.command(
            name="configure-notification",
            description="Configure stream notifications"
        )
        @app_commands.describe(
            platform="Platform (tiktok or twitch)",
            profile_url="Profile URL",
            channel="Channel for notifications",
            role="Role to mention",
            message="Notification message"
        )
        async def configure_notification(
            interaction: discord.Interaction,
            platform: str,
            profile_url: str,
            channel: discord.TextChannel,
            role: discord.Role,
            message: str = "Stream is live!"
        ):
            try:
                await interaction.response.defer(ephemeral=True)
                
                # Validate platform
                if platform.lower() not in ['twitch', 'tiktok']:
                    await interaction.followup.send(
                        "Invalid platform. Supported platforms: twitch, tiktok",
                        ephemeral=True
                    )
                    return

                # Create configuration
                config = {
                    'platform': platform.lower(),
                    'profile_url': profile_url,
                    'channel_id': channel.id,
                    'channel_name': channel.name,
                    'guild_id': interaction.guild_id,
                    'role_id': role.id,
                    'message': message
                }

                # Save configuration
                self.config_service.save_configuration(config)
                
                # Add new configuration to notification service
                await self.notification_service.add_new_configuration(config)

                await interaction.followup.send(
                    f"Configuration saved successfully!\n"
                    f"Platform: {platform}\n"
                    f"Profile: {profile_url}\n"
                    f"Channel: {channel.mention}\n"
                    f"Role: {role.mention}\n"
                    f"Message: {message}",
                    ephemeral=True
                )

            except Exception as e:
                await self.logging_service.log_error(e, "Error configuring notification")
                await interaction.followup.send(
                    "An error occurred while saving the configuration.",
                    ephemeral=True
                )

        @self.tree.command(
            name="configure-intervals",
            description="Configure check intervals for a stream"
        )
        @app_commands.describe(
            profile_url="Stream URL to configure",
            live_interval="Check interval when stream is live (in seconds)",
            offline_interval="Check interval when stream is offline (in seconds)",
            night_interval="Check interval during night mode (in seconds)"
        )
        async def configure_intervals(
            interaction: discord.Interaction,
            profile_url: str,
            live_interval: int = 1800,
            offline_interval: int = 120,
            night_interval: int = 1800
        ):
            try:
                await interaction.response.defer(ephemeral=True)
                
                intervals = {
                    "live": live_interval,
                    "offline": offline_interval,
                    "night": night_interval
                }
                
                self.config_service.update_check_intervals(profile_url, intervals)
                await self.logging_service.log_info(
                    f"Updated check intervals for {profile_url}\n"
                    f"Live: {live_interval}s, Offline: {offline_interval}s, Night: {night_interval}s"
                )
                
                # Przeładuj konfigurację
                self.config_service = ConfigurationService()
                self.logging_service = LoggingService(self, self.config_service)
                self.notification_service = NotificationService(self, self.config_service, self.logging_service)
                
                await interaction.followup.send(
                    f"Check intervals updated for {profile_url}!", 
                    ephemeral=True
                )
                
            except Exception as e:
                await self.logging_service.log_error(e, "Error during interval configuration")
                await interaction.followup.send(
                    "An error occurred while updating intervals.",
                    ephemeral=True
                )

        @self.tree.command(
            name="configure-night-mode",
            description="Configure night mode for a stream"
        )
        @app_commands.describe(
            profile_url="Stream URL to configure",
            enabled="Enable or disable night mode",
            start_hour="Night mode start hour (0-23)",
            end_hour="Night mode end hour (0-23)"
        )
        async def configure_night_mode(
            interaction: discord.Interaction,
            profile_url: str,
            enabled: bool,
            start_hour: int = None,
            end_hour: int = None
        ):
            try:
                await interaction.response.defer(ephemeral=True)
                
                self.config_service.update_night_mode(profile_url, enabled, start_hour, end_hour)
                
                status = "enabled" if enabled else "disabled"
                hours_info = ""
                if start_hour is not None and end_hour is not None:
                    hours_info = f" (from {start_hour}:00 to {end_hour}:00)"
                
                await self.logging_service.log_info(
                    f"Night mode for {profile_url} has been {status}{hours_info}"
                )
                
                # Przeładuj konfigurację
                self.config_service = ConfigurationService()
                self.logging_service = LoggingService(self, self.config_service)
                self.notification_service = NotificationService(self, self.config_service, self.logging_service)
                
                await interaction.followup.send(
                    f"Night mode for {profile_url} has been {status}{hours_info}!", 
                    ephemeral=True
                )
                
            except Exception as e:
                await self.logging_service.log_error(e, "Error during night mode configuration")
                await interaction.followup.send(
                    "An error occurred while configuring night mode.",
                    ephemeral=True
                )

        @self.tree.command(
            name="configure-logging",
            description="Configure logging channel and level"
        )
        @app_commands.describe(
            channel="Channel for logs",
            level="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
        )
        async def configure_logging(
            interaction: discord.Interaction,
            channel: discord.TextChannel,
            level: str = "INFO"
        ):
            try:
                await interaction.response.defer(ephemeral=True)
                
                try:
                    log_level = LogLevel[level.upper()]
                except KeyError:
                    await interaction.followup.send(
                        "Invalid log level! Available levels: DEBUG, INFO, WARNING, ERROR, CRITICAL",
                        ephemeral=True
                    )
                    return

                self.config_service.update_logging_config(channel.id, level)
                
                await self.logging_service.log_info(
                    f"Updated logging configuration\n"
                    f"Channel: {channel.name}\n"
                    f"Level: {level}"
                )
                
                await interaction.followup.send(
                    f"Logging channel has been set to {channel.mention} with level {level}",
                    ephemeral=True
                )
                
            except Exception as e:
                await self.logging_service.log_error(e, "Error during logging configuration")
                await interaction.followup.send(
                    "An error occurred while configuring logging.",
                    ephemeral=True
                )

    async def on_ready(self):
        """Called when the bot is ready"""
        print(f"Bot logged in as {self.user}")
        self._reconnect_counter = 0
        
        # Start checking streams
        try:
            await self.notification_service.start_checking()
            await self.logging_service.log_info("Bot is ready and checking streams")
        except Exception as e:
            await self.logging_service.log_error(e, "Error starting notification service")

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
        self._reconnect_counter += 1
        
        if self._reconnect_counter > self._max_reconnects:
            await self.logging_service.log_error(
                Exception("Przekroczono maksymalną liczbę prób ponownego połączenia"),
                "Bot zostanie zrestartowany"
            )
            # Zatrzymaj bota
            await self.close()
            return

    async def close(self):
        await self.logging_service.log_info("Zatrzymywanie bota...")
        await self.notification_service.stop_checking()
        await super().close()

def run_bot():
    bot = NotificationBot()
    token = os.getenv('DISCORD_TOKEN')
    
    if not token:
        print("Discord token not found in environment variables!")
        return

    try:
        print("Starting bot...")
        bot.run(token, log_handler=None)
    except discord.LoginFailure:
        print("Failed to login. Please check your Discord token.")
    except discord.HTTPException as e:
        print(f"HTTP Exception occurred: {e}")
    except Exception as e:
        print(f"Unexpected error occurred: {e}")
    finally:
        print("Bot shutdown.")

if __name__ == "__main__":
    run_bot() 