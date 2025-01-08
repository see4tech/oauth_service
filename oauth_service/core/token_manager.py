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
        """Encrypt token data for storage."""
        try:
            logger.debug("=== Encrypting Token Data ===")
            json_data = json.dumps(token_data)
            logger.debug(f"Token data serialized, length: {len(json_data)}")
            encrypted = self.fernet.encrypt(json_data.encode())
            logger.debug(f"Token data encrypted, length: {len(encrypted)}")
            return encrypted.decode()
        except Exception as e:
            logger.error(f"Error encrypting token data: {str(e)}")
            raise
    
    def decrypt_token_data(self, encrypted_data: str) -> Dict:
        """Decrypt token data from storage."""
        try:
            logger.debug("=== Decrypting Token Data ===")
            logger.debug(f"Encrypted data length: {len(encrypted_data)}")
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            logger.debug("Successfully decrypted data")
            json_data = decrypted.decode()
            token_data = json.loads(json_data)
            logger.debug(f"Successfully parsed token data with keys: {list(token_data.keys())}")
            return token_data
        except Exception as e:
            logger.error(f"Error decrypting token data: {str(e)}")
            raise
    
    async def store_token(self, platform: str, user_id: str, token_data: Dict) -> None:
        """Store token data in the database."""
        try:
            logger.info(f"=== Storing OAuth Token ===")
            logger.info(f"Platform: {platform}")
            logger.info(f"User ID: {user_id}")
            logger.info(f"Token data keys: {list(token_data.keys())}")
            
            # Encrypt token data before storing
            encrypted_data = self.encrypt_token_data(token_data)
            logger.debug("Token data encrypted successfully")
            
            # Store encrypted token data
            self.db.store_token(user_id, platform, encrypted_data)
            logger.info("Successfully stored encrypted OAuth token")
            
            # Verify storage by retrieving and decrypting
            stored_data = await self.get_token(platform, user_id)
            if stored_data:
                logger.info("Successfully verified token storage and retrieval")
                logger.debug(f"Retrieved token keys: {list(stored_data.keys())}")
            else:
                logger.error("Failed to verify token storage")
            
        except Exception as e:
            logger.error(f"Error storing token: {str(e)}")
            raise

    async def get_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """Get token data for a user."""
        try:
            encrypted_data = self.db.get_token(user_id, platform)
            if encrypted_data:
                logger.debug("Found encrypted token data, attempting to decrypt")
                try:
                    token_data = self.decrypt_token_data(encrypted_data)
                    logger.debug(f"Successfully decrypted token with keys: {list(token_data.keys())}")
                    return token_data
                except Exception as decrypt_error:
                    logger.error(f"Failed to decrypt token: {str(decrypt_error)}")
                    return None
            logger.debug(f"No token found for user {user_id} on platform {platform}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving token: {str(e)}")
            return None

    async def get_valid_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """Get valid token data for a user, refreshing if necessary."""
        try:
            token_data = await self.get_token(platform, user_id)
            if not token_data:
                logger.debug(f"No token found for user {user_id} on platform {platform}")
                return None
            
            # For Twitter, handle OAuth 1.0a and 2.0 separately
            if platform == "twitter":
                oauth2_data = token_data.get('oauth2', {})
                expires_at = oauth2_data.get('expires_at')
                
                if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                    logger.debug(f"OAuth 2.0 token expired for Twitter user {user_id}")
                    refresh_token = oauth2_data.get('refresh_token')
                    if refresh_token:
                        logger.debug(f"Found refresh token for Twitter user {user_id}, attempting refresh")
                        return await self.refresh_token(platform, user_id, token_data)
                    # If no refresh token, but we have OAuth 1.0a tokens, return those
                    if 'oauth1' in token_data:
                        logger.debug(f"No refresh token, but found OAuth 1.0a tokens for user {user_id}")
                        return token_data
                    return None
                return token_data
            
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