from discord import Member, TextChannel
from typing import Dict, List, Tuple

class PermissionChecker:
    REQUIRED_PERMISSIONS = {
        'send_messages': 'Send Messages',
        'embed_links': 'Embed Links',
        'manage_messages': 'Manage Messages',
        'view_channel': 'View Channel'
    }

    @staticmethod
    def check_permissions(member: Member, channel: TextChannel) -> Tuple[bool, str]:
        channel_permissions = channel.permissions_for(member)
        
        permission_status = []
        all_permissions_granted = True
        
        for perm, description in PermissionChecker.REQUIRED_PERMISSIONS.items():
            has_perm = getattr(channel_permissions, perm, False)
            status = "✅" if has_perm else "❌"
            permission_status.append(f"{description}: {status}")
            if not has_perm:
                all_permissions_granted = False

        return all_permissions_granted, "\n".join(permission_status) 