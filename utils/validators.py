import re
from typing import Optional, Tuple

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
    def validate_kick_username(username: str) -> Tuple[bool, str]:
        """
        Validate Kick username according to Kick rules:
        - Length between 3 and 20 characters
        - Only letters, numbers, and underscores
        """
        username = username.lower()
        
        if not 3 <= len(username) <= 20:
            return False, "Kick username must be between 3 and 20 characters long"
        
        if not re.match(r'^[a-zA-Z0-9_]*$', username):
            return False, "Kick username can only contain letters, numbers, and underscores"
        
        return True, "Valid username"


    @staticmethod
    def validate_username(platform: str, username: str) -> Tuple[bool, str]:
        """Validate username based on platform"""
        platform = platform.lower()
        if platform == 'twitch':
            return UsernameValidator.validate_twitch_username(username)
        elif platform == 'tiktok':
            return UsernameValidator.validate_tiktok_username(username)
        elif platform == 'kick':
            return UsernameValidator.validate_kick_username(username)
        else:
            return False, f"Unsupported platform: {platform}"

class Validators:
    """Validation utilities for stream configurations"""

    @staticmethod
    def validate_twitch_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate Twitch URL and extract username
        Returns: (is_valid, username, error_message)
        """
        if not url:
            return False, None, "URL cannot be empty"

        # Remove trailing slash if present
        url = url.rstrip('/')

        # Pattern for twitch URLs
        patterns = [
            r'^(?:https?:\/\/)?(?:www\.)?twitch\.tv\/([a-zA-Z0-9_]{4,25})$',
            r'^([a-zA-Z0-9_]{4,25})$'
        ]

        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                username = match.group(1).lower()
                return True, username, None

        return False, None, "Invalid Twitch URL format"

    @staticmethod
    def validate_tiktok_url(url: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate TikTok URL and extract username
        Returns: (is_valid, username, error_message)
        """
        if not url:
            return False, None, "URL cannot be empty"

        # Remove trailing slash if present
        url = url.rstrip('/')

        # Pattern for TikTok URLs
        patterns = [
            r'^(?:https?:\/\/)?(?:www\.)?tiktok\.com\/@([a-zA-Z0-9_\.]{2,24})$',
            r'^@?([a-zA-Z0-9_\.]{2,24})$'
        ]

        for pattern in patterns:
            match = re.match(pattern, url)
            if match:
                username = match.group(1).lower()
                return True, username, None

        return False, None, "Invalid TikTok URL format"

    @staticmethod
    def validate_platform(platform: str) -> Tuple[bool, Optional[str]]:
        """
        Validate platform name
        Returns: (is_valid, error_message)
        """
        valid_platforms = ['twitch', 'tiktok']
        platform = platform.lower()
        
        if platform not in valid_platforms:
            return False, f"Invalid platform. Supported platforms: {', '.join(valid_platforms)}"
        
        return True, None

    @staticmethod
    def validate_message(message: str) -> Tuple[bool, Optional[str]]:
        """
        Validate notification message
        Returns: (is_valid, error_message)
        """
        if not message:
            return False, "Message cannot be empty"
        
        if len(message) > 1000:
            return False, "Message is too long (max 1000 characters)"
        
        return True, None 