from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class IStreamPlatform(ABC):
    """Interface for stream platforms"""
    
    @abstractmethod
    async def check_stream_status(self, username: str) -> Dict[str, Any]:
        """Check if stream is live"""
        pass

    @abstractmethod
    def get_username_from_url(self, profile_url: str) -> Optional[str]:
        """Extract username from profile URL"""
        pass

    @abstractmethod
    def validate_url(self, profile_url: str) -> bool:
        """Validate profile URL format"""
        pass

    @abstractmethod
    async def get_stream_info(self, username: str) -> Dict[str, Any]:
        """Get detailed stream information"""
        pass 