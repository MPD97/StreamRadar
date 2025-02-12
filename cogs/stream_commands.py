import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from services.stream_service import StreamService
from services.error_handler import ErrorHandler
from .base_commands import BaseCommands
from .stream_embeds import StreamEmbeds

class StreamCommands(BaseCommands):
    def __init__(self, bot, stream_service: StreamService, error_handler: ErrorHandler):
        super().__init__(error_handler)
        self.bot = bot
        self.stream_service = stream_service
        self.embeds = StreamEmbeds()

    @app_commands.command(name="addstream", description="Add new stream to monitoring")
    @app_commands.describe(
        platform="Stream platform (twitch/tiktok)",
        profile_url="Stream profile URL",
        role="Notification role",
        message="Custom notification message"
    )
    async def add_stream_slash(self, interaction: discord.Interaction, 
                             platform: str, profile_url: str,
                             role: discord.Role, message: str):
        await self.handle_command(interaction, self._add_stream_logic, 
                                platform, profile_url, role, message)

    @commands.command(name='addstream')
    @commands.has_permissions(administrator=True)
    async def add_stream(self, ctx, platform: str, profile_url: str, 
                        role: discord.Role, *, message: str):
        await self.handle_command(ctx, self._add_stream_logic, 
                                platform, profile_url, role, message)

    async def _add_stream_logic(self, ctx, platform: str, profile_url: str,
                              role: discord.Role, message: str):
        """Add stream monitoring logic"""
        success = await self.stream_service.add_stream(ctx, platform, profile_url, role, message)
        response = "✅ Stream monitoring added" if success else "❌ Failed to add stream"
        await self.send_response(ctx, f"{response} for {profile_url}")

    @app_commands.command(name="removestream", description="Remove stream from monitoring")
    @app_commands.describe(profile_url="Stream profile URL to remove")
    async def remove_stream_slash(self, interaction: discord.Interaction, profile_url: str):
        await self.handle_command(interaction, self._remove_stream_logic, profile_url)

    @commands.command(name='removestream')
    @commands.has_permissions(administrator=True)
    async def remove_stream(self, ctx, profile_url: str):
        await self.handle_command(ctx, self._remove_stream_logic, profile_url)

    async def _remove_stream_logic(self, ctx, profile_url: str):
        """Remove stream monitoring logic"""
        success = await self.stream_service.remove_stream(ctx, profile_url)
        response = "✅ Stream removed" if success else "❌ Stream not found"
        await self.send_response(ctx, f"{response} from monitoring: {profile_url}")

    @app_commands.command(name="liststreams", description="List all monitored streams")
    async def list_streams_slash(self, interaction: discord.Interaction):
        await self.handle_command(interaction, self._list_streams_logic)

    @commands.command(name='liststreams')
    async def list_streams(self, ctx):
        await self.handle_command(ctx, self._list_streams_logic)

    async def _list_streams_logic(self, ctx):
        """List streams logic"""
        streams = await self.stream_service.get_streams(ctx.guild.id)
        if not streams:
            await self.send_response(ctx, "No streams are being monitored in this server.")
            return

        embed = await self.embeds.create_streams_list_embed(streams, self.stream_service)
        await self.send_response(ctx, "", embed=embed)

    @app_commands.command(name="status", description="Show bot status")
    async def status_slash(self, interaction: discord.Interaction):
        await self.handle_command(interaction, self._status_logic)

    @commands.command(name='status')
    async def status(self, ctx):
        await self.handle_command(ctx, self._status_logic)

    async def _status_logic(self, ctx):
        """Status command logic"""
        streams = await self.stream_service.get_streams(ctx.guild.id)
        embed = self.embeds.create_status_embed(self.bot, len(streams))
        await self.send_response(ctx, "", embed=embed) 