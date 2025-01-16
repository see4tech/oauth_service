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
            # Normalize platform name for Twitter
            if platform == "twitter" and "oauth2" in token_data:
                platform = "twitter-oauth2"
            elif platform == "twitter" and ("oauth1" in token_data or "access_token" in token_data):
                platform = "twitter-oauth1"
                
            logger.debug("\n=== Token Storage Started ===")
            logger.debug(f"Storing token for platform: {platform}, user_id: {user_id}")
            logger.debug(f"Token data keys to store: {list(token_data.keys())}")
            
            token_to_store = token_data.copy()  # Create a copy to avoid modifying the original
            
            # Handle LinkedIn token storage
            if platform == "linkedin":
                logger.debug(f"\n=== LinkedIn Token Storage ===")
                logger.debug(f"Original token data keys: {list(token_data.keys())}")
                logger.debug(f"Original token data: {json.dumps({k: '***' if k in ['access_token', 'refresh_token'] else v for k, v in token_data.items()})}")
                
                # Calculate expires_at if expires_in is present
                if 'expires_in' in token_data:
                    token_to_store['expires_at'] = int(datetime.utcnow().timestamp() + token_data['expires_in'])
                elif 'expires_at' not in token_to_store:
                    # If no expiration info, set a default expiration of 1 hour
                    token_to_store['expires_at'] = int(datetime.utcnow().timestamp() + 3600)
                
                logger.debug(f"Token structure to store: {list(token_to_store.keys())}")
                logger.debug(f"Has refresh token: {'yes' if token_to_store.get('refresh_token') else 'no'}")
                logger.debug(f"Has expires_at: {'yes' if token_to_store.get('expires_at') else 'no'}")
                
            # Handle Twitter OAuth2 token storage
            elif platform == "twitter-oauth2":
                logger.debug("\n=== Twitter OAuth2 Token Storage ===")
                # Ensure token has Bearer prefix
                access_token = token_data.get('access_token', '')
                if not access_token.startswith('Bearer '):
                    token_to_store['access_token'] = f"Bearer {access_token}"
                
                # Calculate expires_at if expires_in is present
                if 'expires_in' in token_data:
                    token_to_store['expires_at'] = int(datetime.utcnow().timestamp() + token_data['expires_in'])
                
                logger.debug(f"Token structure: {list(token_to_store.keys())}")
                logger.debug(f"Has refresh token: {'yes' if token_to_store.get('refresh_token') else 'no'}")
                logger.debug(f"Has expiration: {'yes' if token_to_store.get('expires_at') else 'no'}")
                
            # Handle Twitter OAuth1 token storage
            elif platform == "twitter-oauth1":
                logger.debug("\n=== Twitter OAuth1 Token Storage ===")
                
                # Handle nested oauth1 structure
                if 'oauth1' in token_data:
                    oauth1_data = token_data['oauth1']
                    if not oauth1_data.get('access_token') or not oauth1_data.get('access_token_secret'):
                        raise ValueError("Missing required OAuth1 tokens in nested structure")
                    token_to_store = {
                        'access_token': oauth1_data['access_token'],
                        'token_secret': oauth1_data['access_token_secret']
                    }
                # Handle flat structure
                else:
                    if not token_data.get('access_token') or not token_data.get('token_secret'):
                        raise ValueError("Missing required OAuth1 tokens")
                    token_to_store = token_data
                    
                logger.debug(f"Token structure: {list(token_to_store.keys())}")
            
            # Encrypt token data
            encrypted_data = self.encrypt_token_data(token_to_store)
            
            # Store encrypted token
            success = self.db.store_token(user_id, platform, encrypted_data)
            if success:
                logger.debug(f"Successfully stored {platform} token")
            else:
                logger.error(f"Failed to store {platform} token")
            
        except Exception as e:
            logger.error("\n=== Token Storage Error ===")
            logger.error(f"Error storing token: {str(e)}")
            raise

    async def get_token(self, platform: str, user_id: str) -> Optional[Dict]:
        """Get OAuth tokens for a user."""
        try:
            logger.debug("\n=== Token Retrieval Started ===")
            logger.debug(f"Getting token for platform: {platform}, user_id: {user_id}")
            
            # Get encrypted token data from database
            encrypted_data = self.db.get_token(user_id, platform)
            if not encrypted_data:
                logger.debug("No token data found in database")
                return None
            
            # Decrypt token data
            token_data = self.decrypt_token_data(encrypted_data)
            logger.debug(f"Successfully retrieved token for {platform}")
            logger.debug(f"Token data keys: {list(token_data.keys())}")
            
            # For twitter platform, check if we have old nested structure
            if platform == "twitter" and ("oauth1" in token_data or "oauth2" in token_data):
                logger.debug("Found old nested token structure, please re-authenticate to update token format")
                return None
            
            return token_data
            
        except Exception as e:
            logger.error(f"Error getting token: {str(e)}")
            return None

    async def get_valid_token(self, platform: str, user_id: str, x_api_key: Optional[str] = None) -> Optional[Dict]:
        """
        Get valid token data for a user, refreshing if necessary.
        """
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
                        return await self.refresh_token(platform, user_id, x_api_key)
                    return None
                return token_data
            
            # For Twitter OAuth2, check expiration
            if platform == "twitter-oauth2":
                expires_at = token_data.get('expires_at')
                if expires_at and datetime.fromtimestamp(expires_at) <= datetime.utcnow():
                    logger.debug(f"OAuth 2.0 token expired for Twitter user {user_id}")
                    refresh_token = token_data.get('refresh_token')
                    if refresh_token:
                        logger.debug(f"Found refresh token for Twitter user {user_id}, attempting refresh")
                        return await self.refresh_token(platform, user_id, x_api_key)
                    return None
                return token_data
            
            # For Twitter OAuth1, tokens don't expire
            if platform == "twitter-oauth1":
                return token_data
            
            return token_data
            
        except Exception as e:
            logger.error(f"Error retrieving token: {str(e)}")
            return None
    
    async def refresh_token(self, platform: str, user_id: str, x_api_key: Optional[str] = None) -> Optional[Dict]:
        """Refresh an expired token using the platform's refresh mechanism."""
        try:
            from ..routes.oauth_utils import get_oauth_handler  # Import moved here
            logger.debug(f"Refreshing token for {platform} user {user_id}")
            
            # Get base platform name for OAuth handler
            base_platform = "twitter" if platform.startswith("twitter-") else platform
            
            oauth_handler = await get_oauth_handler(base_platform)
            if not oauth_handler:
                raise Exception("Failed to initialize OAuth handler")
            
            # Get current token data
            token_data = await self.get_token(platform, user_id)
            if not token_data:
                logger.error(f"No token data found for {platform} user {user_id}")
                return None
                
            logger.debug(f"Current token data keys: {list(token_data.keys())}")
            
            # Refresh the token
            new_token_data = await oauth_handler.refresh_token(token_data, x_api_key)
            if not new_token_data:
                logger.error(f"Failed to refresh token for {platform} user {user_id}")
                return None
                
            logger.debug(f"New token data keys: {list(new_token_data.keys())}")
            
            # Store the new token
            await self.store_token(platform, user_id, new_token_data)
            logger.debug(f"Successfully stored refreshed token for {platform}")
            
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