from typing import Dict, Optional
import asyncio
import aiohttp
from datetime import datetime, timedelta
import os
from ..utils.logger import get_logger
from .token_manager import TokenManager
from ..platforms import TwitterOAuth, LinkedInOAuth
from ..core.db import SqliteDB
from ..config import get_settings

logger = get_logger(__name__)

class TokenRefreshService:
    def __init__(self):
        self.token_manager = TokenManager()
        self.running = False
        self.refresh_interval = 300  # 5 minutes

    async def notify_storage_service(self, user_id: str, platform: str, new_token_data: Dict):
        """Notify the storage service about token refresh."""
        try:
            settings = get_settings()
            storage_url = settings.API_KEY_STORAGE
            api_key = settings.API_KEY
            
            if not storage_url or not api_key:
                logger.error("API_KEY_STORAGE or API_KEY not configured")
                return

            # Get user's API key
            db = SqliteDB()
            
            # For Twitter, use the correct platform identifier based on token type
            if platform == "twitter":
                platform_id = "twitter-oauth2" if "oauth2" in new_token_data else "twitter-oauth1"
                user_api_key = db.get_user_api_key(user_id, platform_id)
            else:
                user_api_key = db.get_user_api_key(user_id, platform)
                
            if not user_api_key:
                logger.error("No API key found for user")
                return

            # Prepare token expiration based on platform
            token_expiration = None
            if platform == "twitter" and "oauth2" in new_token_data:
                expires_at = new_token_data["oauth2"].get("expires_at")
                if expires_at:
                    token_expiration = datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M")
            elif platform == "linkedin":
                expires_at = new_token_data.get("expires_at")
                if expires_at:
                    token_expiration = datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M")

            # Send refresh request with existing API key
            async with aiohttp.ClientSession() as session:
                # For Twitter, use the correct platform identifier
                platform_to_use = platform_id if platform == "twitter" else platform
                
                async with session.post(
                    f"{storage_url}/refresh",
                    json={
                        "user_id": user_id,
                        "platform": platform_to_use,
                        "api_key": user_api_key,
                        "token_expiration": token_expiration
                    },
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": api_key
                    }
                ) as response:
                    if not response.ok:
                        logger.error(f"Failed to notify storage service: {await response.text()}")
                    else:
                        logger.info("Successfully notified storage service")
        except Exception as e:
            logger.error(f"Error notifying storage service: {str(e)}")

    async def refresh_token(self, platform: str, user_id: str, token_data: Dict) -> Optional[Dict]:
        """Refresh token for a specific platform."""
        try:
            if platform == "twitter":
                # First, validate we have token data
                if not token_data:
                    logger.error("No token data found for Twitter user")
                    return None

                # Log the token structure we received (safely)
                logger.debug(f"Token data contains keys: {list(token_data.keys())}")
                
                oauth_handler = TwitterOAuth(
                    client_id=os.getenv("TWITTER_CLIENT_ID"),
                    client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
                    callback_url=os.getenv("TWITTER_CALLBACK_URL"),
                    consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
                    consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET")
                )
                
                # Check if we have OAuth 2.0 tokens
                if 'oauth2' not in token_data:
                    logger.error("No OAuth 2.0 token data found for Twitter user")
                    return None
                
                # Check if we have a refresh token
                oauth2_data = token_data['oauth2']
                refresh_token = oauth2_data.get('refresh_token')
                
                # Log token data safely (only show presence/absence and expiry)
                logger.debug("Token data validation:")
                logger.debug("- Has access_token: %s", bool(oauth2_data.get('access_token')))
                logger.debug("- Has refresh_token: %s", bool(refresh_token))
                logger.debug("- Has expiration: %s", bool(oauth2_data.get('expires_at')))
                
                if not refresh_token:
                    logger.error("No Twitter OAuth 2.0 refresh token found")
                    logger.debug("Token data keys available: %s", list(oauth2_data.keys()))
                    return None
                
                logger.debug("Attempting to refresh Twitter OAuth 2.0 token")
                try:
                    new_token_data = await oauth_handler.refresh_token(refresh_token)
                    
                    # Preserve OAuth 1.0a tokens if they exist
                    if 'oauth1' in token_data:
                        new_token_data['oauth1'] = token_data['oauth1']
                        logger.debug("Preserved existing OAuth 1.0a tokens")
                        
                    logger.debug("Successfully refreshed Twitter OAuth 2.0 token")
                    return new_token_data
                except Exception as e:
                    logger.error("Failed to refresh Twitter OAuth 2.0 token: %s", str(e))
                    if hasattr(e, 'response'):
                        logger.error(f"Response status: {e.response.status_code}")
                        logger.error("Response received with error")
                    return None
                    
            elif platform == "linkedin":
                oauth_handler = LinkedInOAuth(
                    client_id=os.getenv("LINKEDIN_CLIENT_ID"),
                    client_secret=os.getenv("LINKEDIN_CLIENT_SECRET"),
                    callback_url=os.getenv("LINKEDIN_CALLBACK_URL")
                )
                if token_data.get('refresh_token'):
                    new_token_data = await oauth_handler.refresh_token(
                        token_data['refresh_token']
                    )
                    return new_token_data

            # Add other platforms as needed
            return None

        except Exception as e:
            if platform == "twitter":
                oauth_type = "OAuth 2.0" if 'oauth2' in token_data else "OAuth 1.0a"
                logger.error("Unexpected error refreshing Twitter %s token: %s", oauth_type, str(e))
                if hasattr(e, 'response'):
                    logger.error(f"Response status: {e.response.status_code}")
                    logger.error("Response received with error")
            else:
                logger.error("Error refreshing token: %s", str(e))
            return None

    async def check_and_refresh_tokens(self):
        """Check all tokens and refresh those that are about to expire."""
        try:
            # Get all tokens from the database
            all_tokens = await self.token_manager.get_all_tokens()
            
            for platform, user_tokens in all_tokens.items():
                for user_id, token_data in user_tokens.items():
                    needs_refresh = False
                    
                    # Skip OAuth 1.0a tokens as they don't expire
                    if platform == "twitter" and 'oauth1' in token_data and 'oauth2' not in token_data:
                        logger.debug("Skipping Twitter OAuth 1.0a token refresh (tokens don't expire)")
                        continue
                    
                    # Check Twitter OAuth 2.0 tokens
                    if platform == "twitter" and 'oauth2' in token_data:
                        expires_at = token_data['oauth2'].get('expires_at')
                        if expires_at and datetime.fromtimestamp(expires_at) - datetime.now() < timedelta(hours=1):
                            logger.info("Twitter OAuth 2.0 token needs refresh")
                            needs_refresh = True
                    
                    # Check LinkedIn tokens
                    elif platform == "linkedin":
                        expires_at = token_data.get('expires_at')
                        if expires_at and datetime.fromtimestamp(expires_at) - datetime.now() < timedelta(hours=1):
                            needs_refresh = True
                    
                    if needs_refresh:
                        logger.info("Refreshing token")
                        new_token_data = await self.refresh_token(platform, user_id, token_data)
                        
                        if new_token_data:
                            # Update token in database
                            await self.token_manager.store_token(platform, user_id, new_token_data)
                            
                            # Notify storage service
                            await self.notify_storage_service(user_id, platform, new_token_data)
                            
                            if platform == "twitter":
                                oauth_type = "OAuth 2.0" if 'oauth2' in new_token_data else "OAuth 1.0a"
                                logger.info("Successfully refreshed Twitter %s token", oauth_type)
                            else:
                                logger.info("Successfully refreshed token")
                        else:
                            if platform == "twitter":
                                oauth_type = "OAuth 2.0" if 'oauth2' in token_data else "OAuth 1.0a"
                                logger.error("Failed to refresh Twitter %s token", oauth_type)
                            else:
                                logger.error("Failed to refresh token")
                            
        except Exception as e:
            logger.error(f"Error in token refresh process: {str(e)}")

    async def start(self):
        """Start the token refresh service."""
        self.running = True
        while self.running:
            await self.check_and_refresh_tokens()
            await asyncio.sleep(self.refresh_interval)

    async def stop(self):
        """Stop the token refresh service."""
        self.running = False

# Global instance
refresh_service = TokenRefreshService()

async def start_refresh_service():
    """Start the token refresh service."""
    await refresh_service.start()

async def stop_refresh_service():
    """Stop the token refresh service."""
    await refresh_service.stop() 