from typing import Dict, Optional
from datetime import datetime
import json
from ..utils.key_manager import KeyManager
from ..core.db import SqliteDB
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TokenManager:
    """Manages OAuth token storage and retrieval with encryption."""
    
    def __init__(self):
        """Initialize token manager with key manager and database."""
        self.key_manager = KeyManager()
        self.fernet = self.key_manager.get_fernet()
        self.db = SqliteDB()
    
    def encrypt_token_data(self, token_data: Dict) -> str:
        """
        Encrypt token data for storage.
        
        Args:
            token_data: Dictionary containing token information
            
        Returns:
            Encrypted token data string
        """
        json_data = json.dumps(token_data)
        return self.fernet.encrypt(json_data.encode()).decode()
    
    def decrypt_token_data(self, encrypted_data: str) -> Dict:
        """
        Decrypt token data from storage.
        
        Args:
            encrypted_data: Encrypted token string
            
        Returns:
            Dictionary containing decrypted token information
        """
        json_data = self.fernet.decrypt(encrypted_data.encode()).decode()
        return json.loads(json_data)
    
    async def store_token(self, platform: str, user_id: str, token_data: Dict) -> None:
        """
        Store encrypted token data in database.
        
        Args:
            platform: Platform identifier (e.g., 'twitter', 'linkedin')
            user_id: User identifier
            token_data: Token information to store
        """
        encrypted_data = self.encrypt_token_data(token_data)
        self.db.store_token(user_id, platform, encrypted_data)
    
    async def get_valid_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """
        Retrieve and validate token data.
        
        Args:
            platform: Platform identifier
            user_id: User identifier
            
        Returns:
            Dictionary containing valid token data or None if not found/invalid
        """
        encrypted_data = self.db.get_token(user_id, platform)
        if not encrypted_data:
            return None
        
        token_data = self.decrypt_token_data(encrypted_data)
        
        # Check token expiration for OAuth 2.0 tokens
        if 'oauth2' in token_data:
            expires_at = token_data['oauth2'].get('expires_at')
            if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                # Token expired, attempt refresh
                return await self.refresh_token(platform, user_id, token_data)
        
        return token_data
    
    async def refresh_token(self, platform: str, user_id: str, token_data: Dict) -> Optional[Dict]:
        """
        Refresh expired token.
        
        Args:
            platform: Platform identifier
            user_id: User identifier
            token_data: Current token data containing refresh token
            
        Returns:
            New token data or None if refresh fails
        """
        try:
            if 'oauth2' not in token_data or 'refresh_token' not in token_data['oauth2']:
                return None
                
            # Platform-specific refresh logic would go here
            # This is a placeholder for actual implementation
            return token_data
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return None
