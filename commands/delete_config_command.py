from discord import app_commands, Interaction
from typing import Literal
import logging

logger = logging.getLogger(__name__)

def setup_delete_config_command(bot):
    @bot.tree.command(
        name="delete-configuration",
        description="Delete a stream notification configuration"
    )
    @app_commands.describe(
        platform="Stream platform (twitch/tiktok/kick)",
        username="Streamer's username to delete configuration for"
    )
    async def delete_configuration(
        interaction: Interaction,
        platform: Literal['twitch', 'tiktok', 'kick'],
        username: str
    ):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.guild_id:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return

            platform = platform.lower()
            if platform == 'tiktok':
                username = username.strip('@')  # Usuń @ jeśli zostało dodane

            # Najpierw sprawdź czy konfiguracja istnieje
            config = await bot.config_service.get_configuration(
                interaction.guild_id, 
                platform,
                username
            )
            
            if not config:
                await interaction.followup.send(
                    f"No configuration found for {platform.capitalize()} streamer {username}.", 
                    ephemeral=True
                )
                return

            # Jeśli konfiguracja istnieje, usuń ją
            deleted = await bot.config_service.delete_configuration(
                interaction.guild_id, 
                platform,
                username
            )
            
            if deleted:
                await bot.notification_service.remove_configuration(
                    interaction.guild_id, 
                    username,
                    platform
                )
                await interaction.followup.send(
                    f"Configuration for {platform.capitalize()} streamer {username} has been deleted.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"Failed to delete configuration for {platform.capitalize()} streamer {username}.", 
                    ephemeral=True
                )

        except Exception as e:
            await bot.logging_service.log_error(e, "Error deleting configuration", interaction.guild_id)
            await interaction.followup.send("An error occurred while deleting the configuration.", ephemeral=True) 