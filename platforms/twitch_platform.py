import aiohttp
from .base_platform import BasePlatform
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class TwitchPlatform(BasePlatform):
    def __init__(self, config_service):
        self.config_service = config_service
        self.client_id = os.getenv('TWITCH_CLIENT_ID')
        self.client_secret = os.getenv('TWITCH_CLIENT_SECRET')
        if not self.client_id or not self.client_secret:
            raise ValueError("Missing TWITCH_CLIENT_ID or TWITCH_CLIENT_SECRET in environment variables!")
        
        self.access_token = None
        self.token_expires_at = None
        self.session = None
        self.headers = {
            'Client-ID': self.client_id,
            'Accept': 'application/json'
        }

    async def initialize(self):
        """Initialize the platform"""
        self.session = aiohttp.ClientSession()

    async def cleanup(self):
        """Cleanup resources"""
        if self.session and not self.session.closed:
            await self.session.close()

    def _extract_username(self, profile_url: str) -> Optional[str]:
        """Extract username from Twitch URL"""
        match = re.search(r'twitch\.tv/([a-zA-Z0-9_]+)', profile_url)
        return match.group(1) if match else None

    async def _ensure_token(self):
        """Ensure we have a valid access token"""
        if not self.session:
            await self.initialize()

        now = datetime.now().timestamp()
        if not self.access_token or (self.token_expires_at and now >= self.token_expires_at):
            params = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials'
            }
            
            async with self.session.post('https://id.twitch.tv/oauth2/token', params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    self.access_token = data['access_token']
                    self.token_expires_at = now + data['expires_in']
                else:
                    raise Exception(f"Failed to get Twitch token: {response.status}")

    async def _get_user_data(self, username: str) -> Optional[Dict[str, Any]]:
        """Get user data from Twitch API"""
        await self._ensure_token()
        
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.access_token}'
        }
        
        url = f'https://api.twitch.tv/helix/users?login={username}'
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                users = data.get('data', [])
                return users[0] if users else None
            elif response.status == 404:
                return None
            else:
                raise Exception(f"Twitch API error: {response.status}")

    async def _get_stream_data(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stream data from Twitch API"""
        await self._ensure_token()
        
        headers = {
            'Client-ID': self.client_id,
            'Authorization': f'Bearer {self.access_token}'
        }
        
        url = f'https://api.twitch.tv/helix/streams?user_id={user_id}'
        async with self.session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                streams = data.get('data', [])
                return streams[0] if streams else None
            else:
                raise Exception(f"Twitch API error: {response.status}")

    async def is_stream_live(self, profile_url: str) -> Dict[str, Any]:
        """Check if stream is live"""
        try:
            username = self._extract_username(profile_url)
            if not username:
                return {
                    'is_live': False,
                    'error': f'Invalid Twitch URL: {profile_url}'
                }

            user_data = await self._get_user_data(username)
            if not user_data:
                return {
                    'is_live': False,
                    'error': f'User not found: {username}'
                }

            stream_data = await self._get_stream_data(user_data['id'])
            
            is_live = bool(stream_data)
            print(f"[Twitch] Check result for {username}: {'Live' if is_live else 'Offline'}")
            
            return {
                'is_live': is_live,
                'user_id': user_data['id'],
                'username': username,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"[Twitch] Error checking {profile_url}: {str(e)}")
            return {
                'is_live': False,
                'error': str(e),
                'username': username if 'username' in locals() else None,
                'timestamp': datetime.now().isoformat()
            } 