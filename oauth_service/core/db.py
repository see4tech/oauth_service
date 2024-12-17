import sqlite3  # Ensure this import is at the top
from pathlib import Path
import threading
from typing import Optional, Dict
import json
import sys
import traceback

# Moved logger import to avoid potential circular imports
from ..utils.logger import get_logger

class SqliteDB:
    """Thread-safe SQLite database manager for OAuth tokens."""
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    # Defer initialization to avoid side effects during import
                    try:
                        cls._instance._lazy_init()
                    except Exception as e:
                        logger = get_logger(__name__)
                        logger.error(f"Error during SqliteDB initialization: {e}")
                        logger.error(traceback.format_exc())
                        raise
        return cls._instance
    
    def _lazy_init(self):
        """Lazy initialization method to avoid side effects during import."""
        if not self._initialized:
            logger = get_logger(__name__)
            logger.info("Initializing SqliteDB")
            
            db_path = Path('data/oauth.db')
            db_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.db_path = db_path
            self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
            self._lock = threading.Lock()
            self._init_db()
            
            self._initialized = True
            logger.info("SqliteDB initialization complete")
    
    def __init__(self):
        # This method is called each time the singleton is accessed
        # We use _lazy_init to ensure thread-safe, one-time initialization
        pass
    
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

# Minimal debug information
def _debug_module_import():
    """
    Helper function to provide minimal debug information about module import
    """
    print(f"Debugging oauth_service.core.db module import")
    print(f"Current module in sys.modules: {__name__}")
    print(f"Module file: {__file__}")

# Call debug function during module import
_debug_module_import()

# Create a module-level instance for easy access
try:
    db = SqliteDB()
except Exception as e:
    print(f"Error creating database instance: {e}")
    db = None

def get_db():
    """
    Provides a thread-safe way to access the database
    """
    if db is None:
        raise RuntimeError("Database not initialized")
    return db