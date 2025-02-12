import sqlite3
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiosqlite

class DatabaseService:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize database tables"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                # Create servers table
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS servers (
                        guild_id INTEGER PRIMARY KEY,
                        name TEXT NOT NULL,
                        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        settings TEXT DEFAULT '{}'
                    )
                ''')

                # Create stream_configs table with all required columns
                await db.execute('''
                    CREATE TABLE IF NOT EXISTS stream_configs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        guild_id INTEGER NOT NULL,
                        platform TEXT NOT NULL,
                        profile_url TEXT NOT NULL,
                        channel_id INTEGER NOT NULL,
                        channel_name TEXT NOT NULL,
                        role_id INTEGER NOT NULL,
                        role_name TEXT NOT NULL,
                        message TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        is_live BOOLEAN DEFAULT 0,
                        should_notify BOOLEAN DEFAULT 1,
                        error_message TEXT,
                        last_check TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(guild_id, profile_url)
                    )
                ''')

                # Add missing columns if they don't exist
                columns_to_add = [
                    ('error_message', 'TEXT'),
                    ('should_notify', 'BOOLEAN DEFAULT 1'),
                    ('is_live', 'BOOLEAN DEFAULT 0'),
                    ('last_check', 'TIMESTAMP')
                ]

                for column_name, column_type in columns_to_add:
                    try:
                        await db.execute(f'''
                            ALTER TABLE stream_configs
                            ADD COLUMN {column_name} {column_type}
                        ''')
                    except aiosqlite.OperationalError as e:
                        if "duplicate column name" in str(e).lower():
                            pass  # column already exists
                        else:
                            raise e

                await db.commit()

    async def add_or_update_server(self, guild_id: int, name: str):
        """Add or update server information"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO servers (guild_id, name)
                    VALUES (?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        name = excluded.name
                ''', (guild_id, name))
                await db.commit()

    async def get_server_configurations(self, guild_id: int) -> List[Dict[str, Any]]:
        """Get all configurations for a server"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = self._dict_factory
                async with db.execute('''
                    SELECT *,
                           datetime(last_check) as last_check,
                           datetime(created_at) as created_at,
                           datetime(updated_at) as updated_at
                    FROM stream_configs
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return rows

    # Alias dla kompatybilności
    async def get_server_configs(self, guild_id: int) -> List[Dict[str, Any]]:
        """Alias for get_server_configurations"""
        return await self.get_server_configurations(guild_id)

    def _dict_factory(self, cursor, row):
        """Custom row factory that handles datetime conversion"""
        d = {}
        for idx, col in enumerate(cursor.description):
            value = row[idx]
            if col[0] in ('last_check', 'created_at', 'updated_at') and value is not None:
                try:
                    d[col[0]] = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    d[col[0]] = None
            else:
                d[col[0]] = value
        return d

    async def add_stream_config(self, config: Dict[str, Any]):
        """Add new stream configuration"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO stream_configs (
                        guild_id, platform, profile_url, channel_id,
                        channel_name, role_id, message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    config['guild_id'],
                    config['platform'],
                    config['profile_url'],
                    config['channel_id'],
                    config['channel_name'],
                    config['role_id'],
                    config.get('message', 'Stream is live!')
                ))
                await db.commit()

    async def update_stream_status(self, guild_id: int, profile_url: str, is_live: bool, notify: bool = True):
        """Update stream live status and notification flag"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE stream_configs
                    SET is_live = ?,
                        should_notify = ?,
                        last_check = CURRENT_TIMESTAMP
                    WHERE guild_id = ? AND profile_url = ?
                ''', (is_live, notify, guild_id, profile_url))
                await db.commit()

    async def get_stream_status(self, guild_id: int, profile_url: str) -> Dict[str, Any]:
        """Get stream status including notification flag"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = self._dict_factory
                async with db.execute('''
                    SELECT is_live, should_notify, last_check
                    FROM stream_configs
                    WHERE guild_id = ? AND profile_url = ?
                ''', (guild_id, profile_url)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else {
                        'is_live': False,
                        'should_notify': True,
                        'last_check': None
                    }

    async def get_all_active_configs(self) -> List[Dict[str, Any]]:
        """Get all active stream configurations across all servers"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT * FROM stream_configs
                    WHERE is_active = 1
                ''') as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

    async def set_logging_channel(self, guild_id: int, channel_id: int, log_level: str = 'INFO'):
        """Set logging channel for a server"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    INSERT INTO logging_configs (guild_id, channel_id, log_level)
                    VALUES (?, ?, ?)
                    ON CONFLICT(guild_id) DO UPDATE SET
                        channel_id = excluded.channel_id,
                        log_level = excluded.log_level,
                        updated_at = CURRENT_TIMESTAMP
                ''', (guild_id, channel_id, log_level))
                await db.commit()

    async def get_logging_config(self, guild_id: int) -> Optional[Dict[str, Any]]:
        """Get logging configuration for a server"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT * FROM logging_configs
                    WHERE guild_id = ?
                ''', (guild_id,)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None

    async def update_configuration_status(self, guild_id: int, profile_url: str, is_active: bool, error_message: str = None):
        """Update configuration status and error message"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute('''
                    UPDATE stream_configs
                    SET is_active = ?,
                        error_message = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE guild_id = ? AND profile_url = ?
                ''', (is_active, error_message, guild_id, profile_url))
                await db.commit()

    async def delete_configuration(self, guild_id: int, profile_url: str) -> bool:
        """Delete a configuration"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute('''
                    DELETE FROM stream_configs
                    WHERE guild_id = ? AND profile_url = ?
                ''', (guild_id, profile_url))
                await db.commit()
                return cursor.rowcount > 0

    async def get_configuration(self, guild_id: int, profile_url: str) -> Optional[Dict[str, Any]]:
        """Get specific configuration"""
        async with self._lock:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute('''
                    SELECT * FROM stream_configs
                    WHERE guild_id = ? AND profile_url = ?
                ''', (guild_id, profile_url)) as cursor:
                    row = await cursor.fetchone()
                    return dict(row) if row else None 