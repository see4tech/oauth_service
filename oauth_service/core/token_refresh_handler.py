from typing import Dict, Optional
from datetime import datetime
import asyncio
from ..utils.logger import get_logger
from .token_manager import TokenManager
from ..core.db import SqliteDB

logger = get_logger(__name__)

class TokenRefreshHandler:
    """Handles token refresh logic for all platforms."""
    
    def __init__(self):
        self.token_manager = TokenManager()
        self.db = SqliteDB()
        self._locks = {}  # Dictionary to store locks for each user_id/platform combination
    
    def _get_lock(self, user_id: str, platform: str) -> asyncio.Lock:
        """Get or create a lock for a specific user_id/platform combination."""
        key = f"{user_id}:{platform}"
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
    
    def _is_token_expired(self, token_data: Dict, platform: str) -> bool:
        """Check if the token is expired based on platform-specific logic."""
        try:
            if platform == "twitter-oauth1":
                return False  # OAuth1 tokens never expire
            elif platform == "twitter-oauth2":
                expires_at = token_data.get('expires_at')
                if expires_at is None:
                    return False  # If no expiration, assume valid
                return datetime.fromtimestamp(expires_at) <= datetime.utcnow()
            elif platform == "linkedin":
                # LinkedIn token expiration check
                expires_at = token_data.get('expires_at')
                if expires_at:
                    return datetime.fromtimestamp(expires_at) <= datetime.utcnow()
                return True  # If no expiration found for LinkedIn, assume expired
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking token expiration for {platform}: {str(e)}")
            return True  # Assume expired on error to trigger refresh attempt
    
    async def get_valid_token(self, user_id: str, platform: str, x_api_key: Optional[str] = None) -> Optional[Dict]:
        """
        Get a valid token, refreshing if necessary.
        
        Args:
            user_id: User identifier
            platform: Platform identifier (e.g., "twitter-oauth1", "twitter-oauth2")
            x_api_key: Optional API key for verification
            
        Returns:
            Valid token data or None if unable to get/refresh token
        """
        try:
            # Get lock for this user/platform combination
            async with self._get_lock(user_id, platform):
                logger.debug(f"\n=== Token Validation Process ===")
                logger.debug(f"Platform: {platform}")
                logger.debug(f"User ID: {user_id}")
                logger.debug(f"Has x-api-key: {'yes' if x_api_key else 'no'}")
                
                # Get current token
                token_data = await self.token_manager.get_token(platform, user_id)
                if not token_data:
                    logger.error(f"No token found for user {user_id} on platform {platform}")
                    return None
                
                logger.debug(f"\n=== Current Token Data ===")
                logger.debug(f"Token data keys: {list(token_data.keys())}")
                
                # Verify x-api-key if provided
                if x_api_key:
                    # For Twitter, always validate against twitter-oauth1 API key
                    validation_platform = "twitter-oauth1" if platform.startswith("twitter") else platform
                    stored_api_key = self.db.get_user_api_key(user_id, validation_platform)
                    logger.debug(f"\n=== API Key Validation ===")
                    logger.debug(f"Validating against platform: {validation_platform}")
                    
                    if not stored_api_key:
                        logger.error(f"No API key found for user {user_id} on platform {validation_platform}")
                        return None
                    if stored_api_key != x_api_key:
                        logger.error(f"Invalid x-api-key for user {user_id} on platform {validation_platform}")
                        return None
                    logger.debug("API key validation successful")
                
                # Check if token needs refresh
                is_expired = self._is_token_expired(token_data, platform)
                logger.debug(f"\n=== Token Expiration Check ===")
                logger.debug(f"Token expired: {is_expired}")
                
                if is_expired:
                    logger.debug(f"\n=== Token Refresh Required ===")
                    logger.debug(f"Token expired for user {user_id} on platform {platform}")
                    
                    # Get platform-specific OAuth handler
                    from ..routes.oauth_routes import get_oauth_handler
                    # Use the actual platform, but strip -oauth1/-oauth2 suffix if present
                    base_platform = platform.split('-')[0] if '-' in platform else platform
                    oauth_handler = await get_oauth_handler(base_platform)
                    
                    # Get refresh token based on platform
                    refresh_token = None
                    if platform == "twitter-oauth2":
                        refresh_token = token_data.get('refresh_token')
                    elif platform == "linkedin":
                        refresh_token = token_data.get('refresh_token')
                    
                    logger.debug(f"\n=== Refresh Token Check ===")
                    logger.debug(f"Refresh token found: {'yes' if refresh_token else 'no'}")
                    
                    if not refresh_token:
                        logger.error(f"No refresh token available for user {user_id} on platform {platform}")
                        return None
                    
                    try:
                        # Attempt to refresh the token
                        logger.debug("\n=== Starting Token Refresh ===")
                        logger.debug("Calling OAuth handler refresh_token method")
                        new_token_data = await oauth_handler.refresh_token(refresh_token)
                        logger.debug("\n=== Token Refresh Response ===")
                        logger.debug(f"New token data received: {'yes' if new_token_data else 'no'}")
                        
                        if new_token_data:
                            logger.debug(f"New token data keys: {list(new_token_data.keys())}")
                            logger.debug(f"New refresh token exists: {'yes' if new_token_data.get('refresh_token') else 'no'}")
                            logger.debug(f"New token expiration: {new_token_data.get('expires_at')}")
                        
                        # Store the new token
                        logger.debug("\n=== Storing New Token ===")
                        logger.debug("Calling token_manager.store_token")
                        await self.token_manager.store_token(platform, user_id, new_token_data)
                        logger.debug("Successfully stored new token data in database")
                        
                        logger.debug(f"\n=== Token Refresh Complete ===")
                        logger.debug(f"Successfully refreshed token for user {user_id} on platform {platform}")
                        
                        return new_token_data
                        
                    except Exception as e:
                        logger.error(f"\n=== Token Refresh Error ===")
                        logger.error(f"Failed to refresh token: {str(e)}")
                        if hasattr(e, 'response'):
                            logger.error(f"Response status: {e.response.status_code}")
                            logger.error(f"Response text: {e.response.text}")
                        return None
                
                logger.debug(f"\n=== Using Existing Token ===")
                logger.debug(f"Token is still valid for user {user_id} on platform {platform}")
                return token_data
                
        except Exception as e:
            logger.error(f"\n=== Unexpected Error ===")
            logger.error(f"Error in get_valid_token: {str(e)}")
            return None

# Global instance
refresh_handler = TokenRefreshHandler() 