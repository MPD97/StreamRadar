import discord
from datetime import datetime
from typing import List, Dict, Any

class StreamEmbeds:
    """Class for creating Discord embeds"""
    
    async def create_streams_list_embed(self, configs: List[Dict[str, Any]], notification_service) -> discord.Embed:
        """Create embed for streams list"""
        embed = discord.Embed(
            title="Monitored Streams",
            color=discord.Color.blue()
        )

        for config in configs:
            status = await notification_service.get_stream_status(config)
            status_emoji = "🟢" if status.get('is_live') else "⭕"
            
            embed.add_field(
                name=f"{status_emoji} {config['platform'].capitalize()}",
                value=f"Channel: {config['profile_url']}\n"
                      f"Notification Role: <@&{config['role_id']}>\n"
                      f"Channel: <#{config['channel_id']}>",
                inline=False
            )

        return embed

    def create_status_embed(self, bot, total_streams: int) -> discord.Embed:
        """Create embed for bot status"""
        embed = discord.Embed(
            title="Bot Status",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="Bot Info",
            value=f"Online since: {bot.user.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                  f"Latency: {round(bot.latency * 1000)}ms",
            inline=False
        )
        
        embed.add_field(
            name="Monitoring",
            value=f"Total streams monitored: {total_streams}",
            inline=False
        )
        
        return embed 