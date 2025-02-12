from discord import app_commands, Interaction, TextChannel, Role
from typing import Optional, Literal
from utils.validators import UsernameValidator
import logging

logger = logging.getLogger(__name__)

def setup_add_config_command(bot):
    @bot.tree.command(
        name="add-configuration",
        description="Add a new stream notification configuration"
    )
    @app_commands.describe(
        platform="Stream platform (twitch/tiktok)",
        username="Streamer's username (without @ for TikTok)",
        channel="Channel for notifications",
        role="Role to mention",
        message="Custom notification message"
    )
    async def add_configuration(
        interaction: Interaction,
        platform: Literal['twitch', 'tiktok'],
        username: str,
        channel: TextChannel,
        role: Role,
        message: Optional[str] = None
    ):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.guild_id:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return

            platform = platform.lower()
            username = username.strip('@')  # Usuń @ jeśli zostało dodane

            # Walidacja username
            is_valid, validation_message = UsernameValidator.validate_username(platform, username)
            if not is_valid:
                await interaction.followup.send(
                    f"Invalid username: {validation_message}", 
                    ephemeral=True
                )
                return

            # Sprawdź czy konfiguracja już istnieje
            existing_config = await bot.db_service.get(
                interaction.guild_id,
                platform,
                username
            )
            
            if existing_config:
                await interaction.followup.send(
                    f"Configuration for {platform.capitalize()} streamer {username} already exists.", 
                    ephemeral=True
                )
                return

            # Konstruowanie URL na podstawie platformy
            if platform == 'twitch':
                profile_url = f"https://twitch.tv/{username}"
            else:  # tiktok
                profile_url = f"https://tiktok.com/@{username}"

            config = {
                'guild_id': interaction.guild_id,
                'platform': platform,
                'username': username,
                'profile_url': profile_url,
                'channel_id': channel.id,
                'channel_name': channel.name,
                'role_id': role.id,
                'role_name': role.name,
                'message': message or f"{role.mention} Stream is live!"
            }

            # Zapisz konfigurację w bazie danych
            if await bot.db_service.save(config):
                # Rozpocznij monitorowanie
                await bot.notification_manager.start_monitoring(config)
                
                await interaction.followup.send(
                    f"Stream notification configuration added:\n"
                    f"Platform: {platform.capitalize()}\n"
                    f"Streamer: {username}\n"
                    f"Channel: {channel.mention}\n"
                    f"Role: {role.mention}",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "Failed to save configuration. Please try again.", 
                    ephemeral=True
                )

        except Exception as e:
            error_message = f"Error adding configuration: {str(e)}"
            await bot.logging_service.log_error(error_message)
            await interaction.followup.send(
                "An error occurred while adding the configuration.", 
                ephemeral=True
            ) 