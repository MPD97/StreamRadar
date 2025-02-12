from discord import Embed, Color, Member, TextChannel
from datetime import datetime
from typing import Dict, Any, List

class StatusEmbed:
    @staticmethod
    def create(configs: List[Dict[str, Any]], permission_info: str, has_configs: bool = True) -> Embed:
        embed = Embed(
            title="Stream Notifications Status",
            color=Color.blue(),
            timestamp=datetime.now()
        )

        embed.description = "Current status of stream notifications" if has_configs else "No stream notifications configured for this server."

        if has_configs:
            for config in configs:
                StatusEmbed._add_config_field(embed, config)

        embed.add_field(
            name="Bot Permissions",
            value=permission_info,
            inline=False
        )

        return embed

    @staticmethod
    def _add_config_field(embed: Embed, config: Dict[str, Any]):
        status_emoji = "🟢" if config['is_active'] else "🔴"
        live_status = "🎥 Live" if config.get('is_live') else "⭕ Offline"
        
        last_check = StatusEmbed._format_last_check(config.get('last_check'))
        platform = config['platform'].capitalize()
        username = config['username']

        status_text = [
            f"Status: {status_emoji} {'Active' if config['is_active'] else 'Inactive'}",
            f"Stream: {live_status}",
            f"Channel: <#{config['channel_id']}>",
            f"Role: <@&{config['role_id']}>",
            f"Last Check: {last_check}"
        ]

        if config.get('error_message'):
            status_text.append(f"⚠️ Error: {config['error_message']}")

        embed.add_field(
            name=f"{platform}: {username}",
            value="\n".join(status_text),
            inline=False
        )

    @staticmethod
    def _format_last_check(last_check) -> str:
        if not last_check:
            return 'Never'
            
        if isinstance(last_check, str):
            try:
                return datetime.fromisoformat(last_check).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                return 'Invalid date'
        elif isinstance(last_check, datetime):
            return last_check.strftime('%Y-%m-%d %H:%M:%S')
        
        return 'Unknown' 