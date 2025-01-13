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
            logger.error("Error encrypting token data")
            raise
    
    def decrypt_token_data(self, encrypted_data: str) -> Dict:
        """Decrypt token data from storage."""
        try:
            logger.debug("=== Decrypting Token Data ===")
            logger.debug(f"Encrypted data length: {len(encrypted_data)}")
            
            # First try to parse as JSON (for old unencrypted data)
            try:
                token_data = json.loads(encrypted_data)
                logger.debug("Data was not encrypted, parsed directly as JSON")
                logger.debug(f"Token data keys: {list(token_data.keys())}")
                return token_data
            except json.JSONDecodeError:
                # If it's not valid JSON, try to decrypt
                logger.debug("Data appears to be encrypted, attempting to decrypt")
                decrypted = self.fernet.decrypt(encrypted_data.encode())
                logger.debug("Successfully decrypted data")
                json_data = decrypted.decode()
                token_data = json.loads(json_data)
                logger.debug(f"Successfully parsed token data with keys: {list(token_data.keys())}")
                return token_data
        except Exception as e:
            logger.error("Error decrypting token data")
            raise
    
    async def store_token(self, platform: str, user_id: str, token_data: Dict) -> None:
        """Store OAuth tokens for a user."""
        try:
            logger.debug("\n=== Token Storage Started ===")
            logger.debug(f"Storing token for platform: {platform}, user_id: {user_id}")
            logger.debug(f"Token data keys to store: {list(token_data.keys())}")
            
            if platform == "twitter" and "oauth2" in token_data:
                logger.debug("\n=== Twitter OAuth2 Token Storage ===")
                logger.debug(f"OAuth2 token keys: {list(token_data['oauth2'].keys())}")
                logger.debug(f"OAuth2 access token (first 10 chars): {token_data['oauth2'].get('access_token', '')[:10]}...")
                logger.debug(f"OAuth2 refresh token exists: {'yes' if token_data['oauth2'].get('refresh_token') else 'no'}")
                logger.debug(f"OAuth2 token expiration: {token_data['oauth2'].get('expires_at')}")
            
            # Get existing tokens first
            existing_tokens = await self.get_token(platform, user_id) or {}
            
            # Merge with new tokens
            existing_tokens.update(token_data)  # This preserves both oauth1 and oauth2
            
            # Encrypt merged tokens
            encrypted_data = self.encrypt_token_data(existing_tokens)
            
            # Store encrypted token data
            self.db.store_token(user_id, platform, encrypted_data)
            
            # Verify storage by retrieving and decrypting
            stored_data = await self.get_token(platform, user_id)
            if stored_data:
                logger.debug("Successfully verified token storage and retrieval")
                logger.debug(f"Retrieved token keys: {list(stored_data.keys())}")
            else:
                logger.error("Failed to verify token storage")
            
        except Exception as e:
            logger.error("\n=== Token Storage Error ===")
            logger.error(f"Error storing token: {str(e)}")
            raise

    async def get_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """Get token data for a user."""
        try:
            logger.debug("\n=== Token Retrieval Started ===")
            logger.debug(f"Getting token for platform: {platform}, user_id: {user_id}")
            
            encrypted_data = self.db.get_token(user_id, platform)
            if encrypted_data:
                logger.debug("Found encrypted token data, attempting to decrypt")
                try:
                    token_data = self.decrypt_token_data(encrypted_data)
                    logger.debug(f"Successfully decrypted token with keys: {list(token_data.keys())}")
                    
                    # For Twitter, handle nested OAuth structure
                    if platform == "twitter" and "oauth2" in token_data:
                        logger.debug(f"OAuth2 token keys: {list(token_data['oauth2'].keys())}")
                        logger.debug(f"OAuth2 access token (first 10 chars): {token_data['oauth2'].get('access_token', '')[:10]}...")
                        logger.debug(f"OAuth2 refresh token exists: {'yes' if token_data['oauth2'].get('refresh_token') else 'no'}")
                        logger.debug(f"OAuth2 token expiration: {token_data['oauth2'].get('expires_at')}")
                    
                    return token_data
                except Exception as decrypt_error:
                    logger.error(f"Failed to decrypt token: {str(decrypt_error)}")
                    return None
            
            logger.debug(f"No token found for user {user_id} on platform {platform}")
            return None
            
        except Exception as e:
            logger.error(f"\n=== Token Retrieval Error ===")
            logger.error(f"Error getting token: {str(e)}")
            return None

    async def get_valid_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """Get valid token data for a user, refreshing if necessary."""
        try:
            token_data = await self.get_token(platform, user_id)
            if not token_data:
                logger.debug(f"No token found for user {user_id} on platform {platform}")
                return None
            
            # For LinkedIn, check expiration
            if platform == "linkedin":
                expires_at = token_data.get('expires_at')
                if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                    logger.debug(f"Token expired for user {user_id} on platform {platform}")
                    if token_data.get('refresh_token'):
                        return await self.refresh_token(platform, user_id, token_data)
                    return None
                return token_data
            
            # For Twitter, handle OAuth 1.0a and 2.0 separately
            if platform == "twitter":
                oauth2_data = token_data.get('oauth2', {})
                # Handle nested oauth2 structure if present
                if isinstance(oauth2_data, dict) and 'oauth2' in oauth2_data:
                    token_data['oauth2'] = oauth2_data['oauth2']
                    logger.debug("Normalized nested OAuth 2.0 structure")
                
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
                        
                        # Try to decrypt/parse token data
                        try:
                            token_data = self.decrypt_token_data(encrypted_data)
                            tokens[platform][user_id] = token_data
                            logger.debug(f"Successfully processed token for {platform}/{user_id}")
                        except Exception as token_error:
                            logger.warning(f"Could not process token for user {user_id} on platform {platform}: {str(token_error)}")
                            continue
                            
                    except Exception as e:
                        logger.warning(f"Error processing token for {platform}/{user_id}: {str(e)}")
                        continue
            
            return tokens
            
        except Exception as e:
            if "no such table" not in str(e).lower():
                logger.error(f"Error retrieving all tokens: {str(e)}")
            return {}