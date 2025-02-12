from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class IDatabase(ABC):
    """Interface for database operations"""
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize database connection and tables"""
        pass

    @abstractmethod
    async def execute(self, query: str, params: tuple = None) -> Any:
        """Execute database query"""
        pass

    @abstractmethod
    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Fetch single row from database"""
        pass

    @abstractmethod
    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Fetch multiple rows from database"""
        pass

    @abstractmethod
    async def transaction(self) -> Any:
        """Start database transaction"""
        pass 