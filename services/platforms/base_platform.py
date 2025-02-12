from abc import ABC, abstractmethod

class BasePlatform(ABC):
    @abstractmethod
    async def is_stream_live(self, profile_url: str) -> bool:
        """Check if stream is live for given profile URL"""
        pass 