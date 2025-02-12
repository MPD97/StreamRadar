from discord.ext import commands
from discord import app_commands, Interaction
from typing import Any, Callable
from services.error_handler import ErrorHandler

class BaseCommands(commands.Cog):
    """Base class for commands with common functionality"""
    
    def __init__(self, error_handler: ErrorHandler):
        self.error_handler = error_handler

    async def handle_command(self, ctx: Any, command_logic: Callable, *args, **kwargs):
        """Generic command handler with error handling"""
        try:
            await command_logic(ctx, *args, **kwargs)
        except Exception as e:
            await self.error_handler.handle_command_error(ctx, e)

    def is_interaction(self, ctx: Any) -> bool:
        """Check if context is a Discord Interaction"""
        return isinstance(ctx, Interaction)

    async def send_response(self, ctx: Any, content: str, embed: Any = None):
        """Send response handling both regular commands and interactions"""
        if self.is_interaction(ctx):
            if not ctx.response.is_done():
                await ctx.response.send_message(content=content, embed=embed)
            else:
                await ctx.followup.send(content=content, embed=embed)
        else:
            await ctx.send(content=content, embed=embed) 