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
            if platform == "twitter":
                # For Twitter, check OAuth 2.0 token expiration
                oauth2_data = token_data.get('oauth2', {})
                expires_at = oauth2_data.get('expires_at')
                if expires_at:
                    return datetime.fromtimestamp(expires_at) <= datetime.utcnow()
                return True  # If no expiration found, assume expired
                
            elif platform == "linkedin":
                # For LinkedIn, check token expiration
                expires_at = token_data.get('expires_at')
                if expires_at:
                    return datetime.fromtimestamp(expires_at) <= datetime.utcnow()
                return True
                
            elif platform in ["instagram", "facebook"]:
                # For Instagram/Facebook, check long-lived token expiration
                expires_at = token_data.get('expires_at')
                if expires_at:
                    return datetime.fromtimestamp(expires_at) <= datetime.utcnow()
                return False  # If no expiration found, assume valid (60-day tokens)
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking token expiration for {platform}: {str(e)}")
            return True  # Assume expired on error to trigger refresh attempt
    
    async def get_valid_token(self, user_id: str, platform: str, x_api_key: Optional[str] = None) -> Optional[Dict]:
        """
        Get a valid token, refreshing if necessary.
        
        Args:
            user_id: User identifier
            platform: Platform identifier
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
                
                logger.debug(f"Current token data keys: {list(token_data.keys())}")
                if platform == "twitter" and "oauth2" in token_data:
                    logger.debug(f"OAuth2 token keys: {list(token_data['oauth2'].keys())}")
                    logger.debug(f"OAuth2 token expiration: {token_data['oauth2'].get('expires_at')}")
                
                # Verify x-api-key if provided
                if x_api_key:
                    stored_api_key = self.db.get_user_api_key(user_id, platform)
                    if not stored_api_key or stored_api_key != x_api_key:
                        logger.error(f"Invalid x-api-key for user {user_id} on platform {platform}")
                        return None
                
                # Check if token needs refresh
                if self._is_token_expired(token_data, platform):
                    logger.debug(f"\n=== Token Refresh Required ===")
                    logger.debug(f"Token expired for user {user_id} on platform {platform}")
                    
                    # Get platform-specific OAuth handler
                    from ..routes.oauth_routes import get_oauth_handler
                    oauth_handler = await get_oauth_handler(platform)
                    
                    # Get refresh token based on platform
                    refresh_token = None
                    if platform == "twitter":
                        oauth2_data = token_data.get('oauth2', {})
                        refresh_token = oauth2_data.get('refresh_token')
                        logger.debug(f"Twitter OAuth2 refresh token found: {'yes' if refresh_token else 'no'}")
                    else:
                        refresh_token = token_data.get('refresh_token')
                    
                    if not refresh_token:
                        logger.error(f"No refresh token available for user {user_id} on platform {platform}")
                        return None
                    
                    try:
                        # Attempt to refresh the token
                        logger.debug("Attempting token refresh")
                        new_token_data = await oauth_handler.refresh_token(refresh_token)
                        
                        if platform == "twitter":
                            # Preserve OAuth 1.0a tokens if they exist
                            if 'oauth1' in token_data:
                                new_token_data['oauth1'] = token_data['oauth1']
                                logger.debug("Preserved OAuth 1.0a tokens")
                        
                        # Store the new token
                        await self.token_manager.store_token(platform, user_id, new_token_data)
                        
                        logger.debug(f"Successfully refreshed token for user {user_id} on platform {platform}")
                        logger.debug(f"New token data keys: {list(new_token_data.keys())}")
                        if platform == "twitter" and "oauth2" in new_token_data:
                            logger.debug(f"New OAuth2 token keys: {list(new_token_data['oauth2'].keys())}")
                            logger.debug(f"New OAuth2 token expiration: {new_token_data['oauth2'].get('expires_at')}")
                        
                        return new_token_data
                        
                    except Exception as e:
                        logger.error(f"Failed to refresh token: {str(e)}")
                        if hasattr(e, 'response'):
                            logger.error(f"Response status: {e.response.status_code}")
                            logger.error(f"Response text: {e.response.text}")
                        return None
                
                logger.debug(f"Token is still valid for user {user_id} on platform {platform}")
                return token_data
                
        except Exception as e:
            logger.error(f"Error in get_valid_token: {str(e)}")
            return None

# Global instance
refresh_handler = TokenRefreshHandler() 