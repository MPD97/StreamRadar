import discord
from datetime import datetime
from typing import Dict, Any, List

class EmbedBuilder:
    """Utility class for building Discord embeds"""

    def async_create_stream_notification(self, config: Dict[str, Any], 
                                      stream_info: Dict[str, Any]) -> discord.Embed:
        """Create stream notification embed"""
        embed = discord.Embed(
            title=stream_info.get('title', 'Stream Started!'),
            description=config.get('message', ''),
            color=self._get_platform_color(config['platform']),
            timestamp=datetime.now()
        )

        self._add_stream_fields(embed, config, stream_info)
        self._add_footer(embed, config)
        
        if thumbnail_url := stream_info.get('thumbnail_url'):
            embed.set_thumbnail(url=thumbnail_url)

        return embed

    def create_status_embed(self, streams: List[Dict[str, Any]], 
                          total_monitored: int) -> discord.Embed:
        """Create status information embed"""
        embed = discord.Embed(
            title="Stream Monitoring Status",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        self._add_status_fields(embed, streams, total_monitored)
        return embed

    def _add_stream_fields(self, embed: discord.Embed, 
                          config: Dict[str, Any], 
                          stream_info: Dict[str, Any]) -> None:
        """Add stream information fields to embed"""
        embed.add_field(
            name="Channel",
            value=f"[{config['username']}]({config['profile_url']})",
            inline=True
        )

        if game := stream_info.get('game'):
            embed.add_field(name="Game", value=game, inline=True)

        if viewers := stream_info.get('viewers'):
            embed.add_field(name="Viewers", value=str(viewers), inline=True)

    def _add_status_fields(self, embed: discord.Embed,
                          streams: List[Dict[str, Any]],
                          total_monitored: int) -> None:
        """Add status information fields to embed"""
        live_streams = sum(1 for s in streams if s.get('is_live', False))
        
        embed.add_field(
            name="Monitored Streams",
            value=str(total_monitored),
            inline=True
        )
        
        embed.add_field(
            name="Currently Live",
            value=str(live_streams),
            inline=True
        )

    def _add_footer(self, embed: discord.Embed, config: Dict[str, Any]) -> None:
        """Add footer to embed"""
        embed.set_footer(
            text=f"Platform: {config['platform'].capitalize()}"
        )

    def _get_platform_color(self, platform: str) -> discord.Color:
        """Get color for platform"""
        colors = {
            'twitch': discord.Color.purple(),
            'youtube': discord.Color.red(),
            'tiktok': discord.Color.dark_theme()
        }
        return colors.get(platform.lower(), discord.Color.blue()) 