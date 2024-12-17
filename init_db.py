"""
Database initialization script to be run from project root.
"""
import sqlite3
from pathlib import Path
import os

def init_db():
    # Create data directory if it doesn't exist
    data_dir = Path('data')
    keys_dir = data_dir / '.keys'
    
    data_dir.mkdir(exist_ok=True)
    keys_dir.mkdir(exist_ok=True)
    
    # Set permissions for .keys directory (Unix-like systems only)
    if os.name == 'posix':
        os.chmod(keys_dir, 0o700)
    
    # Initialize SQLite database
    db_path = data_dir / 'oauth.db'
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create oauth_tokens table
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
    
    conn.commit()
    conn.close()
    
    print("Database initialized successfully!")
    print(f"Database location: {db_path}")
    print(f"Keys directory: {keys_dir}")

if __name__ == "__main__":
    init_db()
