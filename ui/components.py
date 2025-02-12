from discord import ButtonStyle, Interaction, ui
from typing import Dict, Any
import discord

class DeleteConfigButton(ui.Button):
    def __init__(self, config: Dict[str, Any], bot):
        platform = config['platform'].capitalize()
        username = config['username']
        
        super().__init__(
            label=f"Delete {platform}: {username}",
            style=discord.ButtonStyle.danger,
            custom_id=f"delete_config_{config['id']}"
        )
        
        self.config = config
        self.bot = bot

    async def callback(self, interaction: Interaction):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "Nie masz uprawnień do usuwania konfiguracji.", 
                ephemeral=True
            )
            return

        try:
            deleted = await self.bot.config_service.delete_configuration(
                self.config['guild_id'], 
                self.config['platform'],
                self.config['username']
            )

            if deleted:
                await self.bot.notification_service.remove_configuration(
                    self.config['guild_id'], 
                    self.config['username'],
                    self.config['platform']
                )
                await interaction.response.send_message(
                    f"Konfiguracja dla streamera `{self.config['username']}` została usunięta.", 
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"Nie udało się usunąć konfiguracji dla streamera `{self.config['username']}`.", 
                    ephemeral=True
                )

        except Exception as e:
            await self.bot.logging_service.log_error(
                e, 
                f"Error deleting configuration for {self.config['username']}", 
                self.config['guild_id']
            )
            await interaction.response.send_message(
                "Wystąpił błąd podczas usuwania konfiguracji.", 
                ephemeral=True
            )

class StatusView(ui.View):
    def __init__(self, configs: list[Dict[str, Any]], bot):
        super().__init__(timeout=None)
        for config in configs:
            self.add_item(DeleteConfigButton(config, bot)) 