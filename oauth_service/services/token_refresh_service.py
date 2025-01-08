from datetime import datetime, timedelta
import asyncio
from typing import List, Dict
from ..core.token_manager import TokenManager
from ..utils.logger import get_logger
from ..core.db import SqliteDB

logger = get_logger(__name__)

class TokenRefreshService:
    def __init__(self):
        self.token_manager = TokenManager()
        self.db = SqliteDB()
        # Check tokens that will expire in the next 2 days
        self.expiry_threshold = timedelta(days=2)
    
    async def check_and_refresh_tokens(self):
        """Check all tokens and refresh those nearing expiration."""
        try:
            logger.info("=== Starting Daily Token Refresh Check ===")
            tokens = await self.token_manager.get_all_tokens()
            
            for platform, user_tokens in tokens.items():
                logger.info(f"Checking {platform} tokens...")
                for user_id, token_data in user_tokens.items():
                    await self._process_user_token(platform, user_id, token_data)
                    
            logger.info("Token refresh check completed")
            
        except Exception as e:
            logger.error(f"Error during token refresh check: {str(e)}")
    
    async def _process_user_token(self, platform: str, user_id: str, token_data: Dict):
        """Process and refresh a single user's token if needed."""
        try:
            # Get expiration time based on platform
            expires_at = self._get_token_expiration(platform, token_data)
            if not expires_at:
                return
                
            expiry_date = datetime.fromtimestamp(expires_at)
            time_until_expiry = expiry_date - datetime.utcnow()
            
            if time_until_expiry <= self.expiry_threshold:
                logger.info(f"{platform} token for user {user_id} will expire in {time_until_expiry}")
                
                # Refresh token while maintaining the same x-api-key
                new_token_data = await self.token_manager.refresh_token(platform, user_id, token_data)
                if new_token_data:
                    logger.info(f"Successfully refreshed {platform} token for user {user_id}")
                else:
                    logger.error(f"Failed to refresh {platform} token for user {user_id}")
                    
        except Exception as e:
            logger.error(f"Error processing {platform} token for user {user_id}: {str(e)}")
    
    def _get_token_expiration(self, platform: str, token_data: Dict) -> int:
        """Get token expiration timestamp based on platform."""
        if platform == "linkedin":
            return token_data.get('expires_at')
        elif platform == "twitter":
            oauth2_data = token_data.get('oauth2', {})
            return oauth2_data.get('expires_at')
        # Add other platforms as needed
        return None 