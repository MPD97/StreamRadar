from discord import app_commands, Interaction
from typing import Optional
from ui.embeds import StatusEmbed
from ui.components import StatusView
from utils.permissions import PermissionChecker
import logging

logger = logging.getLogger(__name__)

def setup_status_command(bot):
    @bot.tree.command(
        name="status",
        description="Show status of stream notifications for this server"
    )
    async def status(interaction: Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            if not interaction.guild_id:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return

            guild = interaction.guild
            if not guild.me:
                await interaction.followup.send("Bot is not a member of this guild.", ephemeral=True)
                return

            _, permission_info = PermissionChecker.check_permissions(guild.me, interaction.channel)
            configs = await bot.config_service.get_server_configurations(interaction.guild_id)
            
            embed = StatusEmbed.create(configs, permission_info, bool(configs))
            
            if configs:
                view = StatusView(configs, bot)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            await bot.logging_service.log_error(e, "Error showing status", interaction.guild_id)
            await interaction.followup.send("An error occurred while getting status.", ephemeral=True) 