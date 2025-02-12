import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Union
from services.logging_service import LoggingService

class ErrorHandler:
    """Handles command errors and logs them"""

    def __init__(self, logging_service: LoggingService):
        self.logging_service = logging_service
        self.logger = logging.getLogger(__name__)

    async def handle_command_error(self, 
                                 ctx: Union[commands.Context, discord.Interaction], 
                                 error: Union[commands.CommandError, app_commands.AppCommandError]) -> None:
        """Handle command errors and send appropriate responses"""
        try:
            # Log the error
            await self.logging_service.log_error(error, "Command error")

            # Get error message
            error_message = self._get_error_message(error)

            # Send error message
            if isinstance(ctx, discord.Interaction):
                if ctx.response.is_done():
                    await ctx.followup.send(error_message, ephemeral=True)
                else:
                    await ctx.response.send_message(error_message, ephemeral=True)
            else:
                await ctx.send(error_message)

        except Exception as e:
            self.logger.error(f"Error in error handler: {e}")

    def _get_error_message(self, 
                          error: Union[commands.CommandError, app_commands.AppCommandError]) -> str:
        """Get user-friendly error message"""
        if isinstance(error, (commands.MissingPermissions, app_commands.MissingPermissions)):
            return "❌ You don't have permission to use this command."
            
        elif isinstance(error, (commands.BotMissingPermissions, app_commands.BotMissingPermissions)):
            return "❌ I don't have the required permissions to execute this command."
            
        elif isinstance(error, (commands.MissingRole, app_commands.MissingRole)):
            return "❌ You need a specific role to use this command."
            
        elif isinstance(error, (commands.NoPrivateMessage, app_commands.NoPrivateMessage)):
            return "❌ This command can only be used in servers."
            
        elif isinstance(error, (commands.CommandOnCooldown, app_commands.CommandOnCooldown)):
            return f"❌ Please wait {error.retry_after:.1f}s before using this command again."
            
        elif isinstance(error, (ValueError, TypeError)):
            return f"❌ Invalid input: {str(error)}"
            
        elif isinstance(error, app_commands.TransformerError):
            return f"❌ Invalid input format: {str(error)}"
            
        else:
            # Log unexpected errors
            self.logger.error(f"Unexpected error: {type(error).__name__}: {str(error)}")
            return "❌ An unexpected error occurred. Please try again later." 