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

    @staticmethod
    def create_stream_notification(config: Dict[str, Any], stream_info: Dict[str, Any]) -> discord.Embed:
        """Create stream notification embed"""
        embed = discord.Embed(
            title=f"🔴 {config['username']} is now live!",
            url=config['profile_url'],
            color=0x6441A4 if config['platform'] == 'twitch' else 0x000000
        )

        if config['platform'] == 'twitch':
            embed.add_field(
                name="Stream Title", 
                value=stream_info.get('title', 'No title'),
                inline=False
            )
            embed.add_field(
                name="Playing", 
                value=stream_info.get('game_name', 'No game'),
                inline=True
            )
            embed.add_field(
                name="Viewers", 
                value=str(stream_info.get('viewer_count', 0)),
                inline=True
            )
            if thumbnail_url := stream_info.get('thumbnail_url'):
                embed.set_thumbnail(url=thumbnail_url)

        return embed

    @staticmethod
    def create_status_embed(configs: list, permission_info: str, has_configs: bool) -> discord.Embed:
        """Create status embed"""
        if not has_configs:
            embed = discord.Embed(
                title="Stream Notifications Status",
                description="No active stream notifications configured.",
                color=0x808080
            )
            embed.add_field(
                name="Bot Permissions",
                value=permission_info,
                inline=False
            )
            return embed

        embed = discord.Embed(
            title="Stream Notifications Status",
            color=0x00FF00
        )

        for config in configs:
            status = "🟢 Active" if config.get('is_active', True) else "🔴 Inactive"
            live_status = "🔴 Live" if config.get('is_live', False) else "⚫ Offline"
            
            embed.add_field(
                name=f"{config['platform'].capitalize()} - {config['username']}",
                value=f"Channel: <#{config['channel_id']}>\n"
                      f"Role: <@&{config['role_id']}>\n"
                      f"Status: {status}\n"
                      f"Stream: {live_status}",
                inline=True
            )

        embed.add_field(
            name="Bot Permissions",
            value=permission_info,
            inline=False
        )

        return embed 