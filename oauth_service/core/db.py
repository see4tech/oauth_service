# import sqlite3
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
                    cls._instance._lazy_init()
        return cls._instance
    
    def _lazy_init(self):
        """Lazy initialization method to avoid side effects during import."""
        if not self._initialized:
            try:
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
            except Exception as e:
                logger = get_logger(__name__)
                logger.error(f"Error initializing SqliteDB: {e}")
                logger.error(traceback.format_exc())
                raise
    
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
    
    # ... (rest of the methods remain the same)

    def __del__(self):
        """Ensure database connection is closed."""
        if hasattr(self, 'conn'):
            self.conn.close()

# Debug import information
def _debug_module_import():
    """
    Helper function to provide debug information about module import
    """
    print(f"Debugging oauth_service.core.db module import")
    print(f"Current module in sys.modules: {__name__}")
    print(f"Module file: {__file__}")
    
    # Print import stack trace
    print("\nImport Traceback:")
    traceback.print_stack()

# Call debug function during module import
_debug_module_import()

# Create a module-level instance for easy access
db = SqliteDB()

def get_db():
    """
    Provides a thread-safe way to access the database
    """
    return db