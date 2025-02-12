from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class IStreamRepository(ABC):
    """Interface for stream data storage"""
    
    @abstractmethod
    async def save(self, config: Dict[str, Any]) -> None:
        """Save stream configuration"""
        pass

    @abstractmethod
    async def get(self, guild_id: int, profile_url: str) -> Optional[Dict[str, Any]]:
        """Get stream configuration"""
        pass

    @abstractmethod
    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all stream configurations"""
        pass

    @abstractmethod
    async def delete(self, guild_id: int, profile_url: str) -> None:
        """Delete stream configuration"""
        pass

    @abstractmethod
    async def update_status(self, guild_id: int, platform: str, 
                          username: str, is_live: bool) -> None:
        """Update stream status"""
        pass 