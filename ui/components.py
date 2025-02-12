import discord
from discord import ui
from typing import Dict, Any, List

class DeleteConfigButton(ui.Button):
    def __init__(self, config: Dict[str, Any], bot: discord.Client):
        self.config = config
        self.bot = bot
        super().__init__(
            style=discord.ButtonStyle.danger,
            label=f"Delete {config['platform'].capitalize()}: {config['username']}"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle button click"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Użyj db_service zamiast config_service
            deleted = await self.bot.db_service.delete(
                self.config['guild_id'],
                self.config['platform'],
                self.config['username']
            )

            if deleted:
                # Zatrzymaj monitorowanie
                await self.bot.notification_manager.stop_monitoring(self.config)

                # Spróbuj zaktualizować widok
                try:
                    self.disabled = True
                    await interaction.message.edit(view=self.view)
                except discord.NotFound:
                    # Ignoruj błąd jeśli wiadomość została usunięta
                    pass
                except Exception as e:
                    await self.bot.logging_service.log_error(f"Error updating view: {str(e)}")

                await interaction.followup.send(
                    f"Configuration for {self.config['platform'].capitalize()} "
                    f"streamer {self.config['username']} has been deleted.",
                    ephemeral=True
                )

            else:
                await interaction.followup.send(
                    f"Failed to delete configuration for {self.config['platform'].capitalize()} "
                    f"streamer {self.config['username']}.",
                    ephemeral=True
                )

        except Exception as e:
            error_message = f"[Components] Error deleting configuration: {str(e)}"
            await self.bot.logging_service.log_error(error_message)
            await interaction.followup.send(
                "An error occurred while deleting the configuration.",
                ephemeral=True
            )

class StatusView(ui.View):
    def __init__(self, configs: List[Dict[str, Any]], bot: discord.Client):
        super().__init__(timeout=900.0)  # 15 minut timeout
        self.configs = configs
        self.bot = bot

        # Dodaj przyciski dla każdej konfiguracji
        for config in configs:
            self.add_item(DeleteConfigButton(config, bot))

    async def on_timeout(self) -> None:
        """Handle view timeout"""
        for item in self.children:
            item.disabled = True
        
        # Spróbuj zaktualizować wiadomość, jeśli jeszcze istnieje
        try:
            if hasattr(self, 'message'):
                await self.message.edit(view=self)
        except discord.NotFound:
            # Ignoruj błąd jeśli wiadomość została usunięta
            pass
        except Exception as e:
            # Loguj inne błędy
            if hasattr(self, 'bot'):
                await self.bot.logging_service.log_error(f"Error in view timeout: {str(e)}") 