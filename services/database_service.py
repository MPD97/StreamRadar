import sqlite3
import json
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import aiosqlite
import logging
from interfaces.database_interface import IDatabase
from interfaces.repository_interface import IStreamRepository

logger = logging.getLogger(__name__)

class SQLiteDatabase(IStreamRepository):
    """SQLite database implementation"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)
        self._db = None

    async def initialize(self) -> None:
        """Initialize database and create tables if they don't exist"""
        try:
            self._db = await aiosqlite.connect(self.db_path)
            await self._create_tables()
            self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise

    async def close(self) -> None:
        """Close database connection"""
        if self._db:
            try:
                await self._db.close()
                self.logger.info("Database connection closed")
            except Exception as e:
                self.logger.error(f"Error closing database: {e}")
                raise

    async def execute(self, query: str, params: tuple = None) -> Any:
        """Execute database query"""
        try:
            async with self._db.cursor() as cursor:
                await cursor.execute(query, params or ())
                await self._db.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"Query execution error: {e}")
            raise

    async def fetch_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Fetch single row from database"""
        try:
            async with self._db.cursor() as cursor:
                cursor.row_factory = self._dict_factory
                await cursor.execute(query, params or ())
                return await cursor.fetchone()
        except Exception as e:
            self.logger.error(f"Fetch one error: {e}")
            raise

    async def fetch_all(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Fetch multiple rows from database"""
        try:
            async with self._db.cursor() as cursor:
                cursor.row_factory = self._dict_factory
                await cursor.execute(query, params or ())
                return await cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Fetch all error: {e}")
            raise

    async def transaction(self):
        """Context manager for database transactions"""
        return self._db

    async def _create_tables(self) -> None:
        """Create necessary tables"""
        try:
            async with self._db.cursor() as cursor:
                # Create stream_configs table
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS stream_configs (
                        guild_id INTEGER NOT NULL,
                        platform TEXT NOT NULL,
                        username TEXT NOT NULL,
                        profile_url TEXT NOT NULL,
                        channel_id INTEGER NOT NULL,
                        channel_name TEXT NOT NULL,
                        role_id INTEGER NOT NULL,
                        role_name TEXT NOT NULL,
                        message TEXT,
                        is_live BOOLEAN DEFAULT FALSE,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (guild_id, platform, username)
                    )
                """)

                # Sprawdź czy kolumna is_live istnieje
                await cursor.execute("""
                    SELECT COUNT(*) FROM pragma_table_info('stream_configs') 
                    WHERE name='is_live'
                """)
                if (await cursor.fetchone())[0] == 0:
                    await cursor.execute("""
                        ALTER TABLE stream_configs 
                        ADD COLUMN is_live BOOLEAN DEFAULT FALSE
                    """)

                await self._db.commit()
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            raise

    @staticmethod
    def _dict_factory(cursor: aiosqlite.Cursor, row: tuple) -> Dict[str, Any]:
        """Convert SQL row to dictionary"""
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    async def save(self, config: Dict[str, Any]) -> bool:
        """Save stream configuration"""
        try:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    INSERT INTO stream_configs (
                        guild_id, platform, username, profile_url,
                        channel_id, channel_name, role_id, role_name, message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    config['guild_id'], config['platform'], config['username'],
                    config['profile_url'], config['channel_id'], config['channel_name'],
                    config['role_id'], config['role_name'], config['message']
                ))
                await self._db.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}")
            return False

    async def get(self, guild_id: int, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """Get specific stream configuration"""
        try:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    SELECT * FROM stream_configs 
                    WHERE guild_id = ? AND platform = ? AND username = ?
                """, (guild_id, platform, username))
                row = await cursor.fetchone()
                
                if row:
                    columns = [description[0] for description in cursor.description]
                    return dict(zip(columns, row))
                return None
        except Exception as e:
            self.logger.error(f"Error getting configuration: {e}")
            return None

    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all stream configurations"""
        try:
            async with self._db.cursor() as cursor:
                await cursor.execute("SELECT * FROM stream_configs WHERE is_active = TRUE")
                rows = await cursor.fetchall()
                
                if rows:
                    columns = [description[0] for description in cursor.description]
                    return [dict(zip(columns, row)) for row in rows]
                return []
        except Exception as e:
            self.logger.error(f"Error getting all configurations: {e}")
            return []

    async def delete(self, guild_id: int, platform: str, username: str) -> bool:
        """Delete stream configuration"""
        try:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    DELETE FROM stream_configs 
                    WHERE guild_id = ? AND platform = ? AND username = ?
                """, (guild_id, platform, username))
                await self._db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error deleting configuration: {e}")
            return False

    async def update_status(self, guild_id: int, platform: str, username: str, is_live: bool) -> bool:
        """Update stream live status"""
        try:
            async with self._db.cursor() as cursor:
                await cursor.execute("""
                    UPDATE stream_configs 
                    SET is_live = ?
                    WHERE guild_id = ? AND platform = ? AND username = ?
                """, (1 if is_live else 0, guild_id, platform, username))
                await self._db.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error updating status: {e}")
            return False

class DatabaseService:
    def __init__(self):
        self.db_path = 'bot_data.db'
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Initialize the database"""
        async with aiosqlite.connect(self.db_path) as db:
            # Tworzenie tabel jeśli nie istnieją
            await db.execute('''
                CREATE TABLE IF NOT EXISTS stream_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    username TEXT NOT NULL,
                    profile_url TEXT NOT NULL,
                    channel_id INTEGER NOT NULL,
                    channel_name TEXT NOT NULL,
                    role_id INTEGER NOT NULL,
                    role_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(guild_id, platform, username)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS stream_status (
                    guild_id INTEGER NOT NULL,
                    platform TEXT NOT NULL,
                    username TEXT NOT NULL,
                    is_live BOOLEAN NOT NULL,
                    last_check TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (guild_id, platform, username)
                )
            ''')
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
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = self._dict_factory
            async with db.execute('''
                SELECT c.*, s.is_live, s.last_check
                FROM stream_configs c
                LEFT JOIN stream_status s 
                ON c.guild_id = s.guild_id 
                AND c.platform = s.platform 
                AND c.username = s.username
                WHERE c.guild_id = ?
            ''', (guild_id,)) as cursor:
                return await cursor.fetchall()

    # Alias dla kompatybilności
    async def get_server_configs(self, guild_id: int) -> List[Dict[str, Any]]:
        """Alias for get_server_configurations"""
        return await self.get_server_configurations(guild_id)

    def _dict_factory(self, cursor, row):
        """Convert row to dictionary"""
        d = {}
        for idx, col in enumerate(cursor.description):
            value = row[idx]
            if isinstance(value, bytes):
                value = value.decode()
            d[col[0]] = value
        return d

    async def add_stream_config(self, config: Dict[str, Any]):
        """Add stream configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO stream_configs 
                (guild_id, platform, username, profile_url, channel_id, channel_name, role_id, role_name, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                config['guild_id'],
                config['platform'],
                config['username'],
                config['profile_url'],
                config['channel_id'],
                config['channel_name'],
                config['role_id'],
                config['role_name'],
                config['message']
            ))
            await db.commit()

    async def save_stream_state(self, guild_id: int, platform: str, username: str, is_live: bool) -> None:
        """Save stream state"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO stream_status (guild_id, platform, username, is_live)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(guild_id, platform, username) DO UPDATE SET
                    is_live = excluded.is_live,
                    last_check = CURRENT_TIMESTAMP
            ''', (guild_id, platform, username, 1 if is_live else 0))
            await db.commit()

    async def update_configuration_status(self, guild_id: int, platform: str, username: str, 
                                       is_active: bool, error_message: Optional[str] = None) -> None:
        """Update configuration status"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE stream_configs 
                SET is_active = ?, error_message = ?
                WHERE guild_id = ? AND platform = ? AND username = ?
            ''', (1 if is_active else 0, error_message, guild_id, platform, username))
            await db.commit()

    async def get_stream_status(self, guild_id: int, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """Get stream status"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = self._dict_factory
            async with db.execute('''
                SELECT * FROM stream_status
                WHERE guild_id = ? AND platform = ? AND username = ?
            ''', (guild_id, platform, username)) as cursor:
                return await cursor.fetchone()

    async def get_all_active_configs(self) -> List[Dict[str, Any]]:
        """Get all active configurations"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = self._dict_factory
            async with db.execute('''
                SELECT c.*, s.is_live, s.last_check
                FROM stream_configs c
                LEFT JOIN stream_status s 
                ON c.guild_id = s.guild_id 
                AND c.platform = s.platform 
                AND c.username = s.username
                WHERE c.is_active = 1
            ''') as cursor:
                return await cursor.fetchall()

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

    async def delete_configuration(self, guild_id: int, platform: str, username: str) -> bool:
        """Delete configuration"""
        async with aiosqlite.connect(self.db_path) as db:
            # Najpierw sprawdź czy konfiguracja istnieje
            async with db.execute('''
                SELECT id FROM stream_configs 
                WHERE guild_id = ? AND platform = ? AND username = ?
            ''', (guild_id, platform, username)) as cursor:
                if not await cursor.fetchone():
                    return False  # Konfiguracja nie istnieje
            
            # Jeśli konfiguracja istnieje, usuń ją
            await db.execute('''
                DELETE FROM stream_configs 
                WHERE guild_id = ? AND platform = ? AND username = ?
            ''', (guild_id, platform, username))
            
            await db.execute('''
                DELETE FROM stream_status 
                WHERE guild_id = ? AND platform = ? AND username = ?
            ''', (guild_id, platform, username))
            
            await db.commit()
            return True 

    async def get_configuration(self, guild_id: int, platform: str, username: str) -> Optional[Dict[str, Any]]:
        """Get specific configuration by username and platform"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = self._dict_factory
            async with db.execute('''
                SELECT c.*, s.is_live, s.last_check
                FROM stream_configs c
                LEFT JOIN stream_status s 
                ON c.guild_id = s.guild_id 
                AND c.platform = s.platform 
                AND c.username = s.username
                WHERE c.guild_id = ? AND c.platform = ? AND c.username = ?
            ''', (guild_id, platform, username)) as cursor:
                return await cursor.fetchone() 