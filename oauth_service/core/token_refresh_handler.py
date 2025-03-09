from typing import Dict, Optional
from datetime import datetime
import asyncio
from ..utils.logger import get_logger
from .token_manager import TokenManager
from ..core.db import SqliteDB
import json

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
                # If no expiration found for LinkedIn, check expires_in
                expires_in = token_data.get('expires_in')
                if expires_in:
                    # Calculate expiration from expires_in
                    expires_at = int(datetime.utcnow().timestamp() + expires_in)
                    return False  # Token is fresh since we just got expires_in
                return False  # If no expiration info at all, assume valid
            
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
                if x_api_key:
                    logger.debug(f"x-api-key: {x_api_key[:5]}...{x_api_key[-5:] if len(x_api_key) > 10 else ''}")
                
                # Get current token
                token_data = await self.token_manager.get_token(platform, user_id)
                if not token_data:
                    logger.error(f"No token found for user {user_id} on platform {platform}")
                    return None
                
                logger.debug(f"\n=== Current Token Data ===")
                logger.debug(f"Token data keys: {list(token_data.keys())}")
                
                # Log token details without exposing sensitive information
                safe_token_data = {}
                for k, v in token_data.items():
                    if k in ['access_token', 'refresh_token', 'token_secret']:
                        if v:
                            safe_token_data[k] = f"{v[:5]}...{v[-5:] if len(v) > 10 else ''}"
                        else:
                            safe_token_data[k] = None
                    else:
                        safe_token_data[k] = v
                
                logger.debug(f"Token data values (sanitized): {json.dumps(safe_token_data)}")
                
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
                    
                    # Log API key comparison (sanitized)
                    if stored_api_key:
                        stored_key_preview = f"{stored_api_key[:5]}...{stored_api_key[-5:] if len(stored_api_key) > 10 else ''}"
                        logger.debug(f"Stored API key: {stored_key_preview}")
                        logger.debug(f"API keys match: {stored_api_key == x_api_key}")
                    
                    if stored_api_key != x_api_key:
                        logger.error(f"Invalid x-api-key for user {user_id} on platform {validation_platform}")
                        return None
                    logger.debug("API key validation successful")
                
                # Check if token needs refresh
                is_expired = self._is_token_expired(token_data, platform)
                logger.debug(f"\n=== Token Expiration Check ===")
                logger.debug(f"Token expired: {is_expired}")
                
                # For Twitter OAuth2, log expiration details
                if platform == "twitter-oauth2" and 'expires_at' in token_data:
                    expires_at = token_data['expires_at']
                    now = datetime.utcnow().timestamp()
                    logger.debug(f"Token expires at: {expires_at} (timestamp)")
                    logger.debug(f"Current time: {now} (timestamp)")
                    logger.debug(f"Time until expiration: {expires_at - now} seconds")
                
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
                        logger.debug(f"Twitter OAuth2 refresh token found: {'yes' if refresh_token else 'no'}")
                        if refresh_token:
                            logger.debug(f"Refresh token preview: {refresh_token[:5]}...{refresh_token[-5:] if len(refresh_token) > 10 else ''}")
                    elif platform == "linkedin":
                        refresh_token = token_data.get('refresh_token')
                        logger.debug(f"\n=== LinkedIn Refresh Token Details ===")
                        logger.debug(f"Refresh token found: {'yes' if refresh_token else 'no'}")
                        if refresh_token:
                            logger.debug(f"Refresh token preview: {refresh_token[:5]}...{refresh_token[-5:] if len(refresh_token) > 10 else ''}")
                        logger.debug(f"Refresh token type: {type(refresh_token)}")
                        logger.debug(f"Token data keys: {list(token_data.keys())}")
                    
                    logger.debug(f"\n=== Refresh Token Check ===")
                    logger.debug(f"Refresh token found: {'yes' if refresh_token else 'no'}")
                    
                    if not refresh_token:
                        logger.error(f"No refresh token available for user {user_id} on platform {platform}")
                        return None
                    
                    # Attempt to refresh the token
                    logger.debug(f"\n=== Token Refresh Attempt ===")
                    try:
                        new_token_data = await oauth_handler.refresh_token(token_data, x_api_key)
                        
                        if new_token_data:
                            logger.debug(f"Token refresh successful")
                            logger.debug(f"New token data keys: {list(new_token_data.keys())}")
                            
                            # Store the refreshed token
                            await self.token_manager.store_token(platform, user_id, new_token_data)
                            logger.debug(f"Refreshed token stored successfully")
                            
                            return new_token_data
                        else:
                            logger.error(f"Token refresh failed - no new token data returned")
                            return None
                    except Exception as refresh_error:
                        logger.error(f"Error during token refresh: {str(refresh_error)}")
                        logger.error("Token refresh error details:", exc_info=True)
                        return None
                
                # Token is still valid
                logger.debug(f"Token is valid, no refresh needed")
                return token_data
                
        except Exception as e:
            logger.error(f"Error in get_valid_token: {str(e)}")
            logger.error("Stack trace:", exc_info=True)
            return None

# Global instance
refresh_handler = TokenRefreshHandler() 