# from typing import Dict, Optional
# from datetime import datetime
# import json
# from ..utils.key_manager import KeyManager
# from ..core.db import SqliteDB
# from ..utils.logger import get_logger

# logger = get_logger(__name__)

# class TokenManager:
#     """Manages OAuth token storage and retrieval with encryption."""
    
#     def __init__(self):
#         """Initialize token manager with key manager and database."""
#         self.key_manager = KeyManager()
#         self.fernet = self.key_manager.get_fernet()
#         self.db = SqliteDB()
    
#     def encrypt_token_data(self, token_data: Dict) -> str:
#         """
#         Encrypt token data for storage.
        
#         Args:
#             token_data: Dictionary containing token information
            
#         Returns:
#             Encrypted token data string
#         """
#         json_data = json.dumps(token_data)
#         return self.fernet.encrypt(json_data.encode()).decode()
    
#     def decrypt_token_data(self, encrypted_data: str) -> Dict:
#         """
#         Decrypt token data from storage.
        
#         Args:
#             encrypted_data: Encrypted token string
            
#         Returns:
#             Dictionary containing decrypted token information
#         """
#         json_data = self.fernet.decrypt(encrypted_data.encode()).decode()
#         return json.loads(json_data)
    
#     async def store_token(self, platform: str, user_id: str, token_data: Dict) -> None:
#         """
#         Store encrypted token data in database.
        
#         Args:
#             platform: Platform identifier (e.g., 'twitter', 'linkedin')
#             user_id: User identifier
#             token_data: Token information to store
#         """
#         encrypted_data = self.encrypt_token_data(token_data)
#         self.db.store_token(user_id, platform, encrypted_data)
    
#     async def get_valid_token(self, platform: str, user_id: str) -> Optional[Dict]:
#         """
#         Retrieve and validate token data.
        
#         Args:
#             platform: Platform identifier
#             user_id: User identifier
            
#         Returns:
#             Dictionary containing valid token data or None if not found/invalid
#         """
#         encrypted_data = self.db.get_token(user_id, platform)
#         if not encrypted_data:
#             return None
        
#         token_data = self.decrypt_token_data(encrypted_data)
        
#         # Check token expiration for OAuth 2.0 tokens
#         if 'oauth2' in token_data:
#             expires_at = token_data['oauth2'].get('expires_at')
#             if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
#                 # Token expired, attempt refresh
#                 return await self.refresh_token(platform, user_id, token_data)
        
#         return token_data
    
#     async def refresh_token(self, platform: str, user_id: str, token_data: Dict) -> Optional[Dict]:
#         """
#         Refresh expired token.
        
#         Args:
#             platform: Platform identifier
#             user_id: User identifier
#             token_data: Current token data containing refresh token
            
#         Returns:
#             New token data or None if refresh fails
#         """
#         try:
#             if 'oauth2' not in token_data or 'refresh_token' not in token_data['oauth2']:
#                 return None
                
#             # Platform-specific refresh logic would go here
#             # This is a placeholder for actual implementation
#             return token_data
            
#         except Exception as e:
#             logger.error(f"Error refreshing token: {str(e)}")
#             return None

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
        try:
            # Structure token data for storage
            structured_token = {
                "access_token": token_data.get("access_token"),
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in", 3600),
                "refresh_token": token_data.get("refresh_token"),
                "scope": token_data.get("scope"),
                "expires_at": datetime.utcnow().timestamp() + token_data.get("expires_in", 3600),
                "platform": platform
            }
            
            logger.debug(f"Storing token for user {user_id} on platform {platform}")
            encrypted_data = self.encrypt_token_data(structured_token)
            self.db.store_token(user_id, platform, encrypted_data)
            
        except Exception as e:
            logger.error(f"Error storing token: {str(e)}")
            raise
    
    async def get_valid_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """
        Retrieve and validate token data.
        
        Args:
            platform: Platform identifier
            user_id: User identifier
            
        Returns:
            Dictionary containing valid token data or None if not found/invalid
        """
        try:
            encrypted_data = self.db.get_token(user_id, platform)
            if not encrypted_data:
                logger.debug(f"No token found for user {user_id} on platform {platform}")
                return None
            
            token_data = self.decrypt_token_data(encrypted_data)
            
            # Check token expiration
            expires_at = token_data.get('expires_at')
            if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                logger.debug(f"Token expired for user {user_id} on platform {platform}")
                
                # Attempt to refresh if refresh token exists
                if token_data.get('refresh_token'):
                    refreshed_token = await self.refresh_token(platform, user_id, token_data)
                    if refreshed_token:
                        return refreshed_token
                return None
            
            # Return token in format expected by platform handlers
            return {
                "access_token": token_data["access_token"],
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in"),
                "refresh_token": token_data.get("refresh_token"),
                "scope": token_data.get("scope")
            }
            
        except Exception as e:
            logger.error(f"Error retrieving token: {str(e)}")
            return None
    
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
            refresh_token = token_data.get('refresh_token')
            if not refresh_token:
                logger.debug(f"No refresh token available for user {user_id} on platform {platform}")
                return None
            
            # Get the platform-specific OAuth handler
            from ..routes.oauth_routes import get_oauth_handler
            oauth_handler = await get_oauth_handler(platform)
            
            # Refresh the token
            new_token_data = await oauth_handler.refresh_token(refresh_token)
            
            # Store the new token
            await self.store_token(platform, user_id, new_token_data)
            
            return new_token_data
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return None

    async def delete_token(self, platform: str, user_id: str) -> None:
        """
        Delete token data for a user on a specific platform.
        
        Args:
            platform: Platform identifier
            user_id: User identifier
        """
        try:
            self.db.delete_token(user_id, platform)
            logger.debug(f"Deleted token for user {user_id} on platform {platform}")
        except Exception as e:
            logger.error(f"Error deleting token: {str(e)}")
            raise