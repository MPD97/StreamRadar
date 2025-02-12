from typing import Dict, Any, Optional
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load_config()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config[key] = value
        self._save_config()

    def update(self, values: Dict[str, Any]) -> None:
        """Update multiple configuration values"""
        self._config.update(values)
        self._save_config()

    def get_platform_credentials(self, platform: str) -> Dict[str, str]:
        """Get platform-specific credentials"""
        platform_config = self._config.get('platforms', {}).get(platform, {})
        
        # Also check environment variables
        env_prefix = platform.upper()
        env_credentials = {
            key.replace(f"{env_prefix}_", '').lower(): value
            for key, value in os.environ.items()
            if key.startswith(f"{env_prefix}_")
        }
        
        return {**platform_config, **env_credentials}

    def _load_config(self) -> None:
        """Load configuration from file"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = json.load(f)
            else:
                self._config = self._get_default_config()
                self._save_config()
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self._config = self._get_default_config()

    def _save_config(self) -> None:
        """Save configuration to file"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self._config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration"""
        return {
            'prefix': '!',
            'check_interval': 60,
            'log_level': 'INFO',
            'platforms': {
                'twitch': {},
                'tiktok': {}
            }
        } 