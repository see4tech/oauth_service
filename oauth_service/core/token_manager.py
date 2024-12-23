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
        try:
            json_data = self.fernet.decrypt(encrypted_data.encode()).decode()
            return json.loads(json_data)
        except Exception as e:
            # Check if this is test data
            if encrypted_data == "debug_test_token":
                return {"access_token": "test_token", "token_type": "Bearer"}
            raise
    
    async def store_token(self, platform: str, user_id: str, token_data: Dict) -> None:
        """
        Store encrypted token data in database.
        
        Args:
            platform: Platform identifier (e.g., 'twitter', 'linkedin')
            user_id: User identifier
            token_data: Token information to store
        """
        try:
            logger.debug(f"Storing token for user {user_id} on platform {platform}")
            logger.debug(f"Token data structure: {list(token_data.keys())}")
            
            # Special handling for Twitter's dual OAuth structure
            if platform == 'twitter':
                # Get existing token data if any
                existing_data = None
                try:
                    encrypted_existing = self.db.get_token(user_id, platform)
                    if encrypted_existing:
                        existing_data = self.decrypt_token_data(encrypted_existing)
                except Exception:
                    pass

                structured_token = {}
                
                # Handle OAuth 2.0 tokens
                if 'oauth2' in token_data:
                    oauth2_data = token_data['oauth2']
                    structured_token['oauth2'] = {
                        'access_token': oauth2_data.get('access_token'),
                        'refresh_token': oauth2_data.get('refresh_token'),
                        'expires_in': oauth2_data.get('expires_in', 7200),
                        'expires_at': oauth2_data.get('expires_at') or (
                            datetime.utcnow().timestamp() + oauth2_data.get('expires_in', 7200)
                        )
                    }
                elif existing_data and 'oauth2' in existing_data:
                    structured_token['oauth2'] = existing_data['oauth2']

                # Handle OAuth 1.0a tokens
                if 'oauth1' in token_data:
                    oauth1_data = token_data['oauth1']
                    structured_token['oauth1'] = {
                        'access_token': oauth1_data.get('access_token'),
                        'access_token_secret': oauth1_data.get('access_token_secret')
                    }
                elif existing_data and 'oauth1' in existing_data:
                    structured_token['oauth1'] = existing_data['oauth1']

                structured_token['platform'] = platform
                
            else:
                # Standard OAuth 2.0 structure for other platforms
                structured_token = {
                    'access_token': token_data.get('access_token'),
                    'token_type': token_data.get('token_type', 'Bearer'),
                    'expires_in': token_data.get('expires_in', 3600),
                    'refresh_token': token_data.get('refresh_token'),
                    'scope': token_data.get('scope'),
                    'expires_at': token_data.get('expires_at') or (
                        datetime.utcnow().timestamp() + token_data.get('expires_in', 3600)
                    ),
                    'platform': platform
                }
            
            encrypted_data = self.encrypt_token_data(structured_token)
            self.db.store_token(user_id, platform, encrypted_data)
            logger.debug(f"Successfully stored token with structure: {list(structured_token.keys())}")
            
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
            logger.debug(f"Retrieved token data with keys: {token_data.keys()}")
            
            # For Twitter, we need both OAuth 1.0a and 2.0 tokens
            if platform == 'twitter':
                # Check OAuth 2.0 token expiration if it exists
                if 'oauth2' in token_data:
                    expires_at = token_data.get('expires_at')
                    if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                        logger.debug(f"OAuth 2.0 token expired for user {user_id}")
                        # Attempt to refresh if refresh token exists
                        if token_data.get('refresh_token'):
                            refreshed_token = await self.refresh_token(platform, user_id, token_data)
                            if refreshed_token:
                                # Preserve OAuth 1.0a tokens if they exist
                                if 'oauth1' in token_data:
                                    refreshed_token['oauth1'] = token_data['oauth1']
                                return refreshed_token
                
                # Return both OAuth 1.0a and 2.0 tokens if they exist
                return {
                    'oauth1': token_data.get('oauth1', {}),
                    'oauth2': token_data.get('oauth2', {})
                }
            
            # For other platforms, handle standard OAuth 2.0
            expires_at = token_data.get('expires_at')
            if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                logger.debug(f"Token expired for user {user_id} on platform {platform}")
                if token_data.get('refresh_token'):
                    return await self.refresh_token(platform, user_id, token_data)
                return None
            
            return token_data
            
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

    async def get_all_tokens(self) -> Dict:
        """
        Retrieve all tokens from the database.
        
        Returns:
            Dict: Dictionary with platform as key and user tokens as value
        """
        try:
            tokens = {}
            with self.db._lock:
                cursor = self.db.conn.cursor()
                cursor.execute('''
                    SELECT user_id, platform, token_data
                    FROM oauth_tokens
                    WHERE user_id NOT LIKE 'debug_%'
                    AND user_id NOT LIKE 'test_%'
                ''')
                results = cursor.fetchall()
                
                # Organize tokens by platform and user_id
                for user_id, platform, encrypted_data in results:
                    try:
                        if platform not in tokens:
                            tokens[platform] = {}
                        decrypted_data = self.decrypt_token_data(encrypted_data)
                        tokens[platform][user_id] = decrypted_data
                    except Exception as decrypt_error:
                        # Only log for non-test users
                        if not (user_id.startswith('debug_') or user_id.startswith('test_')):
                            logger.warning(f"Could not decrypt token for user {user_id} on platform {platform}")
                        continue
            
            return tokens
            
        except Exception as e:
            # Log only if it's not a common "no such table" error during initialization
            if "no such table" not in str(e).lower():
                logger.warning("Could not retrieve tokens from database")
            return {}