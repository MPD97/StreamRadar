import re
from typing import Tuple

class UsernameValidator:
    @staticmethod
    def validate_twitch_username(username: str) -> Tuple[bool, str]:
        """
        Validate Twitch username according to Twitch rules:
        - Length between 4 and 25 characters
        - Only letters, numbers, and underscores
        - Must begin with a letter
        """
        if not 4 <= len(username) <= 25:
            return False, "Twitch username must be between 4 and 25 characters long"
        
        if not username[0].isalpha():
            return False, "Twitch username must begin with a letter"
        
        if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', username):
            return False, "Twitch username can only contain letters, numbers, and underscores"
        
        return True, "Valid username"

    @staticmethod
    def validate_tiktok_username(username: str) -> Tuple[bool, str]:
        """
        Validate TikTok username according to TikTok rules:
        - Length between 2 and 24 characters
        - Only letters, numbers, underscores, and periods
        - Cannot begin or end with a period
        - Cannot have consecutive periods
        """
        username = username.strip('@')
        
        if not 2 <= len(username) <= 24:
            return False, "TikTok username must be between 2 and 24 characters long"
        
        if username.startswith('.') or username.endswith('.'):
            return False, "TikTok username cannot begin or end with a period"
        
        if '..' in username:
            return False, "TikTok username cannot contain consecutive periods"
        
        if not re.match(r'^[a-zA-Z0-9_.]*$', username):
            return False, "TikTok username can only contain letters, numbers, underscores, and periods"
        
        return True, "Valid username"

    @staticmethod
    def validate_username(platform: str, username: str) -> Tuple[bool, str]:
        """Validate username based on platform"""
        platform = platform.lower()
        if platform == 'twitch':
            return UsernameValidator.validate_twitch_username(username)
        elif platform == 'tiktok':
            return UsernameValidator.validate_tiktok_username(username)
        else:
            return False, f"Unsupported platform: {platform}" 