import aiohttp
from .base_platform import BasePlatform
import os
import re
from datetime import datetime, timedelta

class TwitchPlatform(BasePlatform):
    def __init__(self, config_service):
        self.config_service = config_service
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        if not self.client_id or not self.client_secret:
            raise ValueError("Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET in environment variables!")
        
        self.access_token = None
        self.token_expires_at = None
        self.headers = {
            'Client-ID': self.client_id,
            'Accept': 'application/json'
        }

    async def get_access_token(self):
        """Get new access token from Twitch API"""
        try:
            async with aiohttp.ClientSession() as session:
                url = 'https://id.twitch.tv/oauth2/token'
                params = {
                    'client_id': self.client_id,
                    'client_secret': self.client_secret,
                    'grant_type': 'client_credentials'
                }
                
                async with session.post(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.access_token = data['access_token']
                        # Set token expiration (usually 60 days, but we set 50 for safety)
                        self.token_expires_at = datetime.now() + timedelta(days=50)
                        self.headers['Authorization'] = f'Bearer {self.access_token}'
                        print("Successfully refreshed Twitch token")
                    else:
                        error_data = await response.text()
                        raise Exception(f"Error getting Twitch token: {response.status} - {error_data}")
        except Exception as e:
            print(f"Error getting Twitch token: {str(e)}")
            raise

    async def ensure_valid_token(self):
        """Check and refresh token if needed"""
        if not self.access_token or not self.token_expires_at or datetime.now() >= self.token_expires_at:
            await self.get_access_token()

    async def is_stream_live(self, profile_url: str) -> bool:
        try:
            await self.ensure_valid_token()
            
            username = self._extract_username(profile_url)
            if not username:
                print(f"Could not extract username from URL: {profile_url}")
                return False

            async with aiohttp.ClientSession(headers=self.headers) as session:
                # First get user ID
                user_url = f"https://api.twitch.tv/helix/users?login={username}"
                async with session.get(user_url) as response:
                    if response.status == 401:
                        # Token expired or invalid, try to refresh
                        print("Token expired, refreshing...")
                        await self.get_access_token()
                        # Retry with new token
                        return await self.is_stream_live(profile_url)
                    
                    if response.status != 200:
                        error_data = await response.text()
                        print(f"Error getting user data: {response.status} - {error_data}")
                        return False
                    
                    user_data = await response.json()
                    if not user_data.get('data'):
                        print(f"User not found: {username}")
                        return False
                    
                    user_id = user_data['data'][0]['id']
                    
                    # Now check stream status
                    stream_url = f"https://api.twitch.tv/helix/streams?user_id={user_id}"
                    async with session.get(stream_url) as stream_response:
                        if stream_response.status != 200:
                            error_data = await stream_response.text()
                            print(f"Error checking stream status: {stream_response.status} - {error_data}")
                            return False
                        
                        stream_data = await stream_response.json()
                        is_live = bool(stream_data.get('data'))
                        
                        if is_live:
                            print(f"Stream active for {username}")
                        else:
                            print(f"No active stream for {username}")
                        
                        return is_live

        except Exception as e:
            print(f"Error checking Twitch stream: {str(e)}")
            return False

    def _extract_username(self, profile_url: str) -> str:
        """Extract username from Twitch URL"""
        pattern = r'(?:https?://)?(?:www\.)?twitch\.tv/([a-zA-Z0-9_]+)'
        match = re.match(pattern, profile_url)
        return match.group(1) if match else None 