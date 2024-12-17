import sqlite3
from pathlib import Path
import threading
from typing import Optional, Dict
import json
import sys
import traceback
import importlib

# Moved logger import to avoid potential circular imports
from ..utils.logger import get_logger

class SqliteDB:
    """Thread-safe SQLite database manager for OAuth tokens."""
    
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    
    @classmethod
    def get_instance(cls):
        """
        Explicit class method to get or create the singleton instance
        Helps avoid potential import-time initialization issues
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialization method to avoid side effects during import."""
        if not self._initialized:
            logger = get_logger(__name__)
            try:
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
                logger.error(f"Error initializing SqliteDB: {e}")
                logger.error(traceback.format_exc())
                raise
    
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

# Module-level function to get database instance
def get_db():
    """
    Provides a thread-safe way to access the database
    """
    return SqliteDB.get_instance()

# Debugging function
def _debug_module_import():
    """
    Helper function to provide minimal debug information about module import
    """
    print(f"Debugging {__name__} module import")
    print(f"Current module in sys.modules: {__name__}")
    print(f"Module file: {__file__}")
    
    # Print some additional context
    print(f"Caller's module: {sys._getframe(1).f_globals.get('__name__', 'Unknown')}")

# Conditional debug output
if __name__ == '__main__':
    # Only run debug output when the module is directly executed
    _debug_module_import()
    
    # Demonstrate database usage when run directly
    try:
        db = get_db()
        print("\nDatabase instance created successfully")
        
        # Perform a simple test
        test_user_id = "debug_test_user"
        test_platform = "debug_test_platform"
        test_token = "debug_test_token"
        
        db.store_token(test_user_id, test_platform, test_token)
        retrieved_token = db.get_token(test_user_id, test_platform)
        
        print(f"Test token stored and retrieved: {retrieved_token}")
        assert retrieved_token == test_token, "Token retrieval failed"
    
    except Exception as e:
        print(f"Error during direct module execution: {e}")
        traceback.print_exc()