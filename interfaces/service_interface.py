from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import discord

class IStreamService(ABC):
    """Interface for stream business logic"""
    
    @abstractmethod
    async def add_stream(self, ctx: Any, platform: str, profile_url: str,
                        role: discord.Role, message: str) -> bool:
        """Add new stream to monitoring"""
        pass

    @abstractmethod
    async def remove_stream(self, ctx: Any, profile_url: str) -> bool:
        """Remove stream from monitoring"""
        pass

    @abstractmethod
    async def get_streams(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all streams for guild"""
        pass

    @abstractmethod
    async def get_stream_status(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Get stream status"""
        pass 