import json
from pathlib import Path
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from .database_service import DatabaseService
import logging

logger = logging.getLogger(__name__)

class LogLevel(Enum):
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4

class ConfigurationService:
    DEFAULT_CHECK_INTERVALS = {
        "live": 1800,      # 30 minutes when stream is active
        "offline": 120,    # 2 minutes when stream is offline
        "night": 1800      # 30 minutes in night mode
    }

    DEFAULT_NIGHT_MODE = {
        "enabled": False,
        "start_hour": 20,
        "end_hour": 8
    }

    def __init__(self, db_service: DatabaseService):
        self.db_service = db_service
        self.config_path = Path("config.json")
        self.data = self._load_configurations()

    async def initialize(self):
        """Initialize the configuration service"""
        await self.db_service.initialize()

    def _load_configurations(self):
        """Load configurations from file"""
        default_config = {
            "stream_configs": [],
            "logging_channel": None,
            "log_level": "INFO"
        }
        
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading configuration: {str(e)}")
                return default_config
        return default_config

    def _save_to_file(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")

    async def save_configuration(self, config: Dict[str, Any]):
        """Save stream configuration"""
        await self.db_service.add_stream_config(config)

    async def get_server_configurations(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all configurations for a server"""
        return await self.db_service.get_server_configurations(guild_id)

    async def get_all_configurations(self) -> List[Dict[str, Any]]:
        """Get all active configurations"""
        return await self.db_service.get_all_active_configs()

    async def save_stream_state(self, guild_id: int, platform: str, username: str, is_live: bool):
        """Save stream state"""
        await self.db_service.update_stream_status(guild_id, platform, username, is_live)

    async def set_logging_channel(self, guild_id: int, channel_id: int, log_level: str = 'INFO'):
        """Set logging channel for a server"""
        await self.db_service.set_logging_channel(guild_id, channel_id, log_level)

    async def get_logging_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get logging configuration for a server"""
        return await self.db_service.get_logging_config(guild_id)

    def get_check_interval(self, config):
        """Get appropriate check interval based on current state"""
        current_hour = datetime.now().hour
        is_live = config.get("is_live", False)
        
        if "check_intervals" not in config:
            config["check_intervals"] = self.DEFAULT_CHECK_INTERVALS.copy()
        
        night_mode = config.get("night_mode", self.DEFAULT_NIGHT_MODE.copy())
        
        # Check if night mode is enabled and active
        is_night = (
            night_mode.get("enabled", False) and 
            (current_hour >= night_mode.get("start_hour", 20) or 
             current_hour < night_mode.get("end_hour", 8))
        )
        
        if is_night:
            return config["check_intervals"].get("night", self.DEFAULT_CHECK_INTERVALS["night"])
        elif is_live:
            return config["check_intervals"].get("live", self.DEFAULT_CHECK_INTERVALS["live"])
        else:
            return config["check_intervals"].get("offline", self.DEFAULT_CHECK_INTERVALS["offline"])

    def update_check_intervals(self, profile_url: str, intervals: dict):
        """Update check intervals for specific configuration"""
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url:
                if "check_intervals" not in config:
                    config["check_intervals"] = self.DEFAULT_CHECK_INTERVALS.copy()
                config["check_intervals"].update(intervals)
                self._save_to_file()
                break

    def update_night_mode(self, profile_url: str, enabled: bool, start_hour: int = None, end_hour: int = None):
        """Update night mode settings for specific configuration"""
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url:
                if "night_mode" not in config:
                    config["night_mode"] = self.DEFAULT_NIGHT_MODE.copy()
                
                config["night_mode"]["enabled"] = enabled
                if start_hour is not None:
                    config["night_mode"]["start_hour"] = start_hour
                if end_hour is not None:
                    config["night_mode"]["end_hour"] = end_hour
                
                self._save_to_file()
                break

    def update_room_id(self, profile_url: str, room_id: str):
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url and config['platform'] == 'tiktok':
                config['room_id'] = room_id
                self._save_to_file()
                break

    def get_room_id(self, profile_url: str) -> str:
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url and config['platform'] == 'tiktok':
                return config.get('room_id')
        return None

    def get_logging_channel(self) -> int:
        return self.data.get("logging_channel")

    def get_log_level(self) -> str:
        return self.data.get("log_level", "INFO")

    async def get_stream_status(self, guild_id: int, platform: str, username: str) -> Dict[str, Any]:
        """Get stream status from database"""
        return await self.db_service.get_stream_status(guild_id, platform, username)

    async def get_stream_state(self, guild_id: int, profile_url: str) -> Dict[str, Any]:
        """Get stream state from database"""
        return await self.db_service.get_stream_status(guild_id, profile_url)

    async def update_configuration_status(self, guild_id: int, platform: str, username: str, is_active: bool, error_message: str = None):
        """Update configuration status and error message"""
        await self.db_service.update_configuration_status(guild_id, platform, username, is_active, error_message)

    async def get_configuration(self, guild_id: int, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """Get specific configuration"""
        return await self.db_service.get_configuration(guild_id, platform, username)

    async def delete_configuration(self, guild_id: int, platform: str, username: str) -> bool:
        """Delete a configuration"""
        return await self.db_service.delete_configuration(guild_id, platform, username) 