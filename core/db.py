import sqlite3
from pathlib import Path
import threading
from typing import Optional, Dict
import json
from ..utils.logger import get_logger

logger = get_logger(__name__)

class SqliteDB:
    """Thread-safe SQLite database manager for OAuth tokens."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            db_path = Path('data/oauth.db')
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.db_path = db_path
            self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self._lock = threading.Lock()
            self._init_db()
            self.initialized = True
    
    def _init_db(self):
        """Initialize database tables."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS oauth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    token_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, platform)
                )
            ''')
            self.conn.commit()
    
    def store_token(self, user_id: str, platform: str, token_data: str) -> None:
        """Store encrypted token data."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO oauth_tokens 
                (user_id, platform, token_data, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, platform, token_data))
            self.conn.commit()
    
    def get_token(self, user_id: str, platform: str) -> Optional[str]:
        """Retrieve encrypted token data."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT token_data FROM oauth_tokens
                WHERE user_id = ? AND platform = ?
            ''', (user_id, platform))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def delete_token(self, user_id: str, platform: str) -> None:
        """Delete token data."""
        with self._lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                DELETE FROM oauth_tokens
                WHERE user_id = ? AND platform = ?
            ''', (user_id, platform))
            self.conn.commit()
    
    def __del__(self):
        """Ensure database connection is closed."""
        if hasattr(self, 'conn'):
            self.conn.close()
