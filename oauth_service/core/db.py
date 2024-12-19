import sqlite3
from pathlib import Path
import threading
from typing import Optional, Dict, List
import sys
import traceback
from datetime import datetime

# Lazy logger import to avoid circular dependencies
def _get_logger():
    try:
        from ..utils.logger import get_logger
        return get_logger(__name__)
    except ImportError:
        # Fallback to print if logger can't be imported
        class FallbackLogger:
            def info(self, msg): print(f"INFO: {msg}")
            def error(self, msg): print(f"ERROR: {msg}")
        return FallbackLogger()

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
                    cls._instance._safe_initialize()
        return cls._instance
    
    def _safe_initialize(self):
        """
        Safely initialize the database with minimal side effects
        """
        if not self._initialized:
            try:
                logger = _get_logger()
                logger.info("Initializing SqliteDB")
                
                # Ensure data directory exists
                db_path = Path('data/oauth.db')
                db_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Initialize database connection
                self.db_path = db_path
                self.conn = sqlite3.connect(
                    str(db_path), 
                    check_same_thread=False
                )
                self._lock = threading.Lock()
                
                # Create tables
                self._init_db()
                
                # Mark as initialized
                self._initialized = True
                logger.info("SqliteDB initialization complete")
            
            except Exception as e:
                logger = _get_logger()
                logger.error(f"Error initializing SqliteDB: {e}")
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
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used_at TIMESTAMP,
                    UNIQUE(user_id)
                )
            ''')
            
            # Add indexes if they don't exist
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_oauth_tokens_user_platform 
                ON oauth_tokens(user_id, platform)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_user 
                ON user_api_keys(user_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_key 
                ON user_api_keys(api_key)
            ''')
            
            self.conn.commit()
            
    def store_token(self, user_id: str, platform: str, token_data: str) -> None:
        """
        Store encrypted token data.
        
        Args:
            user_id (str): Unique identifier for the user
            platform (str): Platform name for the token
            token_data (str): Encrypted token data to store
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO oauth_tokens 
                    (user_id, platform, token_data, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (user_id, platform, token_data))
                self.conn.commit()
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error storing token: {e}")
            raise
    
    def get_token(self, user_id: str, platform: str) -> Optional[str]:
        """
        Retrieve encrypted token data.
        
        Args:
            user_id (str): Unique identifier for the user
            platform (str): Platform name for the token
        
        Returns:
            Optional[str]: Retrieved token data or None if not found
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT token_data FROM oauth_tokens
                    WHERE user_id = ? AND platform = ?
                ''', (user_id, platform))
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error retrieving token: {e}")
            raise
    
    def delete_token(self, user_id: str, platform: str) -> None:
        """
        Delete token data.
        
        Args:
            user_id (str): Unique identifier for the user
            platform (str): Platform name for the token
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    DELETE FROM oauth_tokens
                    WHERE user_id = ? AND platform = ?
                ''', (user_id, platform))
                self.conn.commit()
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error deleting token: {e}")
            raise

    def get_user_tokens(self, user_id: str) -> List[Dict]:
        """
        Retrieve all tokens for a user.
        
        Args:
            user_id (str): Unique identifier for the user
        
        Returns:
            List[Dict]: List of token data dictionaries with platform info
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT platform, token_data, updated_at 
                    FROM oauth_tokens
                    WHERE user_id = ?
                ''', (user_id,))
                results = cursor.fetchall()
                return [
                    {
                        'platform': row[0],
                        'token_data': row[1],
                        'updated_at': row[2]
                    }
                    for row in results
                ]
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error retrieving user tokens: {e}")
            raise

    def update_token_timestamp(self, user_id: str, platform: str) -> None:
        """
        Update the timestamp for a token without changing the token data.
        
        Args:
            user_id (str): Unique identifier for the user
            platform (str): Platform name for the token
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    UPDATE oauth_tokens 
                    SET updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND platform = ?
                ''', (user_id, platform))
                self.conn.commit()
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error updating token timestamp: {e}")
            raise
    
    def store_user_api_key(self, user_id: str, api_key: str) -> None:
        """
        Store or update a user's API key.
        
        Args:
            user_id (str): Unique identifier for the user
            api_key (str): Generated API key
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO user_api_keys 
                    (user_id, api_key)
                    VALUES (?, ?)
                ''', (user_id, api_key))
                self.conn.commit()
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error storing user API key: {e}")
            raise
            
    def get_user_api_key(self, user_id: str) -> Optional[str]:
        """
        Retrieve a user's API key.
        
        Args:
            user_id (str): Unique identifier for the user
            
        Returns:
            Optional[str]: The user's API key or None if not found
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT api_key FROM user_api_keys
                    WHERE user_id = ?
                ''', (user_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error retrieving user API key: {e}")
            raise
            
    def validate_user_api_key(self, api_key: str) -> Optional[str]:
        """
        Validate an API key and return the associated user_id.
        
        Args:
            api_key (str): API key to validate
            
        Returns:
            Optional[str]: The user_id associated with the API key or None if invalid
        """
        try:
            with self._lock:
                cursor = self.conn.cursor()
                cursor.execute('''
                    UPDATE user_api_keys 
                    SET last_used_at = CURRENT_TIMESTAMP
                    WHERE api_key = ?
                    RETURNING user_id
                ''', (api_key,))
                result = cursor.fetchone()
                self.conn.commit()
                return result[0] if result else None
        except sqlite3.Error as e:
            logger = _get_logger()
            logger.error(f"Error validating user API key: {e}")
            raise
    
    @classmethod
    def get_instance(cls):
        """
        Get or create the singleton instance of SqliteDB.
        
        Returns:
            SqliteDB: Singleton instance of the database manager
        """
        return cls()
    
    def __del__(self):
        """Ensure database connection is closed."""
        if hasattr(self, 'conn'):
            self.conn.close()

# Module-level function to get database instance
def get_db():
    """
    Provides a thread-safe way to access the database
    
    Returns:
        SqliteDB: Singleton instance of the database manager
    """
    return SqliteDB.get_instance()

# Debugging and import tracking
def _debug_module_import():
    """
    Helper function to provide minimal debug information about module import
    """
    print(f"Debugging {__name__} module import")
    print(f"Current module in sys.modules: {__name__}")
    print(f"Module file: {__file__}")
    
    # Print some additional context
    try:
        caller_module = sys._getframe(1).f_globals.get('__name__', 'Unknown')
        print(f"Caller's module: {caller_module}")
    except Exception:
        print("Could not determine caller module")

# Only run debug output when the module is directly executed
if __name__ == '__main__':
    _debug_module_import()
    
    try:
        # Demonstrate database usage
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
        
        print("\nDatabase test completed successfully")
    
    except Exception as e:
        print(f"Error during direct module execution: {e}")
        traceback.print_exc()