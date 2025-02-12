from typing import Dict, Any, List, Optional

class QueryBuilder:
    """SQL query builder utility"""
    
    @staticmethod
    def insert_stream_config(config: Dict[str, Any]) -> tuple[str, tuple]:
        """Build insert query for stream configuration"""
        query = '''
            INSERT OR REPLACE INTO stream_configs (
                guild_id, platform, username, profile_url,
                channel_id, channel_name, role_id, role_name,
                message, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            config['guild_id'], config['platform'], config['username'],
            config['profile_url'], config['channel_id'], config['channel_name'],
            config['role_id'], config['role_name'], config['message'],
            config.get('is_active', True)
        )
        return query, params

    @staticmethod
    def update_stream_status(guild_id: int, platform: str, 
                           username: str, is_live: bool) -> tuple[str, tuple]:
        """Build update query for stream status"""
        query = '''
            INSERT OR REPLACE INTO stream_status (
                guild_id, platform, username, is_live, last_check
            ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        '''
        params = (guild_id, platform, username, is_live)
        return query, params

    @staticmethod
    def get_stream_config(guild_id: int, profile_url: str) -> tuple[str, tuple]:
        """Build query to get stream configuration"""
        query = '''
            SELECT * FROM stream_configs 
            WHERE guild_id = ? AND profile_url = ?
        '''
        params = (guild_id, profile_url)
        return query, params

    @staticmethod
    def get_all_configs() -> str:
        """Build query to get all configurations"""
        return '''
            SELECT c.*, s.is_live, s.last_check 
            FROM stream_configs c
            LEFT JOIN stream_status s ON 
                c.guild_id = s.guild_id AND 
                c.platform = s.platform AND 
                c.username = s.username
            WHERE c.is_active = 1
        ''' 