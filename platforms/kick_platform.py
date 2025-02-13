from .base_platform import BasePlatform
import re
from typing import Dict, Any, Optional
import traceback
import requests
from datetime import datetime
import random

class KickPlatform(BasePlatform):
    def __init__(self, config_service):
        self.config_service = config_service
    
    async def is_stream_live(self, profile_url: str) -> bool:
        """Main method to check if stream is live"""
        try:
            username = self._extract_username(profile_url)
            if not username:
                print(f"[Kick] Missing username. Profile URL: {profile_url}")
                return False
            
            data = await self._get_stream_data(username)
            return data.get('is_live', False)
            
        except Exception as e:
            print(f"[Kick] Error in is_stream_live: {str(e)}")
            print(f"[Kick] Traceback: {traceback.format_exc()}")
            return False
    
    def _extract_username(self, profile_url: str) -> Optional[str]:
        """Extract username from Kick.com profile URL"""
        pattern = r"kick\.com/([a-zA-Z0-9_-]+)"
        match = re.search(pattern, profile_url)
        
        if not match:
            return None
        
        return match.group(1)
    
    async def _get_stream_data(self, username: str) -> Dict[str, Any]:
        """Get stream data using requests with session"""
        start_time = datetime.now()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Referer': 'https://kick.com/'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        
        try:
            # Najpierw pobieramy główną stronę aby uzyskać ciasteczka
            print("[Kick] Fetching main page for cookies...")
            session.get('https://kick.com/')
            
            # Teraz żądanie API z losowym XSRF token
            api_url = f'https://kick.com/api/v2/channels/{username}'
            print(f"[Kick] Fetching API: {api_url}")
            
            response = session.get(
                api_url,
                headers={'X-XSRF-TOKEN': str(random.randint(10000000, 99999999))}
            )
            
            if response.status_code == 403:
                print("[Kick] Access forbidden - possible Cloudflare block")
                return {
                    'is_live': False,
                    'timestamp': datetime.now().isoformat(),
                    'error': 'Access forbidden - possible Cloudflare block',
                    'status_code': 403
                }
            
            response.raise_for_status()
            data = response.json()
            
            is_live = data.get('livestream') is not None
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"[Kick] Stream status:")
            print(f"[Kick] - Is Live: {is_live}")
            print(f"[Kick] - Check Duration: {duration:.2f} seconds")
            
            result = {
                'is_live': is_live,
                'timestamp': end_time.isoformat(),
                'check_duration': duration,
                'username': username,
                'title': data.get('livestream', {}).get('session_title') if is_live else None,
                'viewers': data.get('livestream', {}).get('viewer_count') if is_live else None,
                'data': data
            }
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"[Kick] Request error: {str(e)}")
            print(f"[Kick] Response status code: {getattr(e.response, 'status_code', 'N/A')}")
            print(f"[Kick] Response text: {getattr(e.response, 'text', 'N/A')}")
            return {
                'is_live': False,
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'status_code': getattr(e.response, 'status_code', None)
            }
            
        except Exception as e:
            print(f"[Kick] Error in _get_stream_data: {str(e)}")
            print(f"[Kick] Traceback: {traceback.format_exc()}")
            return {
                'is_live': False,
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
        