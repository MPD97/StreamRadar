import aiohttp
from bs4 import BeautifulSoup
from .base_platform import BasePlatform
import asyncio
import re
import json
from typing import Optional, Dict, Any
from datetime import datetime
import urllib.parse
import traceback

class TikTokPlatform(BasePlatform):
    def __init__(self, config_service):
        self.config_service = config_service
        self.session = None
        self.last_check = {}
        self.check_interval = 30
        self.cache = {}
        self.cache_duration = 15  # seconds
        self.base_check_url = "https://webcast.tiktok.com/webcast/room/check_alive/"
        self.room_id_cache = {}  # Cache for room IDs
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
        }
        self.max_retries = 10
        self.retry_delay = 1

    async def ensure_session(self):
        """Ensures aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def is_stream_live(self, profile_url: str) -> bool:
        """Main method to check if stream is live"""
        try:
            username = self._extract_username(profile_url)
            if not username:
                print(f"[TikTok] Could not extract username from URL: {profile_url}")
                return False

            # Get room ID
            room_id = await self._get_room_id(username)
            if not room_id:
                print(f"[TikTok] Could not get room ID for username: {username}")
                return False

            # Check stream status
            status = await self._check_stream_status(room_id)
            return status
        
        except Exception as e:
            print(f"[TikTok] Error in is_stream_live: {str(e)}")
            print(f"[TikTok] Traceback: {traceback.format_exc()}")
            return False

    async def _get_room_id(self, username: str) -> Optional[str]:
        """Get room ID for a username"""
        try:
            # Check cache first
            if username in self.room_id_cache:
                return self.room_id_cache[username]

            await self.ensure_session()
            
            print(f"[TikTok] Getting room ID for username: {username}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive'
            }

            url = f'https://www.tiktok.com/@{username}/live'
            print(f"[TikTok] Fetching live page: {url}")

            async with self.session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    text = await response.text()
                    
                    # Try to find room ID in the page content
                    room_id_patterns = [
                        r'"roomId":"(\d+)"',
                        r'"room_id":"(\d+)"',
                        r'room_id=(\d+)',
                        r'roomId=(\d+)'
                    ]
                    
                    for pattern in room_id_patterns:
                        match = re.search(pattern, text)
                        if match:
                            room_id = match.group(1)
                            print(f"[TikTok] Found room ID: {room_id}")
                            self.room_id_cache[username] = room_id
                            return room_id
                    
                    print("[TikTok] Could not find room ID in page content")
                else:
                    print(f"[TikTok] Error getting live page: {response.status}")

            return None

        except Exception as e:
            print(f"[TikTok] Error getting room ID: {str(e)}")
            print(f"[TikTok] Traceback: {traceback.format_exc()}")
            return None

    async def _check_stream_status(self, room_id: str) -> Dict[str, Any]:
        """Check stream status using webcast API"""
        try:
            await self.ensure_session()
            
            print(f"\n[TikTok] Checking stream status for room_id: {room_id}")
            start_time = datetime.now()
            
            params = {
                'aid': '1988',
                'app_language': 'pl-PL',
                'app_name': 'tiktok_web',
                'browser_language': 'pl',
                'browser_name': 'Mozilla',
                'browser_online': 'true',
                'browser_platform': 'Win32',
                'browser_version': '5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
                'channel': 'tiktok_web',
                'cookie_enabled': 'true',
                'device_platform': 'web_pc',
                'focus_state': 'true',
                'from_page': 'user',
                'history_len': '2',
                'is_fullscreen': 'false',
                'is_page_visible': 'true',
                'os': 'windows',
                'region': 'PL',
                'room_ids': room_id,
                'screen_height': '1080',
                'screen_width': '1920',
                'tz_name': 'Europe/Warsaw',
                'webcast_language': 'pl-PL'
            }

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7',
                'Connection': 'keep-alive',
                'Referer': 'https://www.tiktok.com/'
            }

            url = f"{self.base_check_url}?{urllib.parse.urlencode(params)}"
            
            async with self.session.get(url, headers=headers, timeout=10) as response:
                print(f"[TikTok] Response status code: {response.status}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    is_live = False
                    if data.get('data') and isinstance(data['data'], list) and len(data['data']) > 0:
                        is_live = data['data'][0].get('alive', False)
                    
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    
                    print(f"[TikTok] Stream status:")
                    print(f"[TikTok] - Is Live: {is_live}")
                    print(f"[TikTok] - Check Duration: {duration:.2f} seconds")
                    
                    return {
                        'is_live': is_live,
                        'room_id': room_id,
                        'timestamp': end_time.isoformat(),
                        'response_code': response.status,
                        'check_duration': duration,
                        'raw_data': data
                    }
                else:
                    print(f"[TikTok] Error response: {response.status}")
                    return {
                        'is_live': False,
                        'room_id': room_id,
                        'timestamp': datetime.now().isoformat(),
                        'error': f'HTTP {response.status}',
                        'response_code': response.status
                    }

        except Exception as e:
            print(f"[TikTok] Error checking stream status: {str(e)}")
            print(f"[TikTok] Traceback: {traceback.format_exc()}")
            return {
                'is_live': False,
                'room_id': room_id,
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'response_code': None
            }

    async def _fetch_room_id(self, profile_url: str) -> str:
        try:
            live_url = self._get_live_url(profile_url)
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(live_url) as response:
                    if response.status != 200:
                        return None
                    
                    text = await response.text()
                    # Looking for room_id in the response
                    match = re.search(r'"roomId":"(\d+)"', text)
                    if match:
                        return match.group(1)
                    return None
        except Exception as e:
            print(f"Error while fetching room_id: {e}")
            return None

    def _get_live_url(self, profile_url: str) -> str:
        profile_url = profile_url.rstrip('/')
        if profile_url.endswith('/live'):
            return profile_url
        return f"{profile_url}/live"

    def _extract_username(self, profile_url: str) -> Optional[str]:
        """Extract username from TikTok URL"""
        patterns = [
            r'(?:https?://)?(?:www\.)?tiktok\.com/@([a-zA-Z0-9_.]+)(?:/live)?/?',
            r'@([a-zA-Z0-9_.]+)'
        ]
        
        for pattern in patterns:
            match = re.match(pattern, profile_url)
            if match:
                return match.group(1)
        return None

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close() 