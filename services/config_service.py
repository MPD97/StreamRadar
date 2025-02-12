import json
from pathlib import Path
from enum import Enum
from datetime import datetime

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

    def __init__(self):
        self.config_path = Path("config.json")
        self.data = self._load_configurations()

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

    def get_all_configurations(self):
        """Get all stream configurations"""
        return self.data.get("stream_configs", [])

    def save_configuration(self, config):
        """Save new stream configuration"""
        configs = self.data.get("stream_configs", [])
        
        # Update existing config if found
        for i, existing_config in enumerate(configs):
            if existing_config["profile_url"] == config["profile_url"]:
                configs[i] = config
                break
        else:
            # Add new config if not found
            configs.append(config)
        
        self.data["stream_configs"] = configs
        self._save_to_file()

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

    def save_stream_state(self, profile_url: str, is_live: bool):
        """Save current stream state"""
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url:
                config['is_live'] = is_live
                self._save_to_file()
                break

    def get_logging_config(self):
        """Get logging configuration"""
        return {
            'channel_id': self.data.get('logging_channel'),
            'level': self.data.get('log_level', 'INFO')
        }

    def update_logging_config(self, channel_id: int, level: str = "INFO"):
        """Update logging configuration"""
        self.data['logging_channel'] = channel_id
        self.data['log_level'] = level
        self._save_to_file()

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

    def get_stream_state(self, profile_url: str) -> bool:
        """Pobiera zapisany stan transmisji"""
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url:
                return config.get('is_live', False)

    def update_night_mode(self, profile_url: str, enabled: bool, start_hour: int = None, end_hour: int = None):
        """Aktualizuje ustawienia trybu nocnego dla konkretnej konfiguracji"""
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

    def update_check_intervals(self, profile_url: str, intervals: dict):
        """Aktualizuje interwały sprawdzania dla konkretnej konfiguracji"""
        for config in self.data["stream_configs"]:
            if config['profile_url'] == profile_url:
                if "check_intervals" not in config:
                    config["check_intervals"] = self.DEFAULT_CHECK_INTERVALS.copy()
                config["check_intervals"].update(intervals)
                self._save_to_file()
                break 