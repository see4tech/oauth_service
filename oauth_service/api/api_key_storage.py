from typing import Optional
import aiohttp
from ..utils.logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)

class APIKeyStorage:
    def __init__(self):
        self.settings = get_settings()
        self.api_url = self.settings.API_KEY_STORAGE

    async def store_api_key(
        self,
        user_id: str,
        platform: str,
        api_key: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None
    ) -> bool:
        """Store API key and tokens in external storage service."""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "user_id": user_id,
                    "platform": platform,
                    "api_key": api_key,
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in
                }
                
                headers = {
                    "Content-Type": "application/json",
                    "x-api-key": self.settings.API_KEY  # Add the service API key
                }
                
                async with session.post(
                    f"{self.api_url}/store", 
                    json=data,
                    headers=headers
                ) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        logger.error(f"Failed to store API key. Status: {response.status}, Response: {response_text}")
                        raise ValueError(f"Failed to store API key: {response_text}")
                    
                    logger.info(f"Successfully stored API key for user {user_id} and platform {platform}")
                    return True
                    
        except Exception as e:
            logger.error(f"Error storing API key: {str(e)}")
            raise  # Re-raise the exception to be handled by the caller 