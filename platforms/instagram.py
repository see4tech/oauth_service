from typing import Dict, Optional
import aiohttp
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger

logger = get_logger(__name__)

class InstagramOAuth(OAuthBase):
    """Instagram OAuth 2.0 implementation using Facebook Graph API."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="instagram")
        self.auth_url = "https://api.instagram.com/oauth/authorize"
        self.token_url = "https://api.instagram.com/oauth/access_token"
        self.graph_url = "https://graph.instagram.com/v12.0"
    
    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get Instagram authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL string
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "scope": "user_profile,user_media",
            "response_type": "code",
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        return f"{self.auth_url}?{query}"
    
    async def get_access_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Dictionary containing access token and related data
        """
        async with aiohttp.ClientSession() as session:
            # First, exchange code for short-lived access token
            async with session.post(
                self.token_url,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.crypto.decrypt(self._client_secret),
                    "grant_type": "authorization_code",
                    "redirect_uri": self.callback_url,
                    "code": code
                }
            ) as response:
                data = await response.json()
                short_lived_token = data["access_token"]
                
                # Exchange short-lived token for long-lived token
                async with session.get(
                    "https://graph.instagram.com/access_token",
                    params={
                        "grant_type": "ig_exchange_token",
                        "client_secret": self.crypto.decrypt(self._client_secret),
                        "access_token": short_lived_token
                    }
                ) as long_lived_response:
                    long_lived_data = await long_lived_response.json()
                    return {
                        "access_token": long_lived_data["access_token"],
                        "token_type": "bearer",
                        "expires_in": long_lived_data["expires_in"],
                        "user_id": data["user_id"]
                    }
    
    async def refresh_token(self, access_token: str) -> Dict:
        """
        Refresh long-lived access token.
        
        Args:
            access_token: Current long-lived access token
            
        Returns:
            Dictionary containing new access token data
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://graph.instagram.com/refresh_access_token",
                params={
                    "grant_type": "ig_refresh_token",
                    "access_token": access_token
                }
            ) as response:
                data = await response.json()
                return {
                    "access_token": data["access_token"],
                    "token_type": "bearer",
                    "expires_in": data["expires_in"]
                }
    
    async def create_media_container(self, token: str, media_url: str, 
                                   caption: str) -> Dict:
        """
        Create a media container for Instagram post.
        
        Args:
            token: Access token
            media_url: URL of the media to post
            caption: Post caption
            
        Returns:
            Dictionary containing media container ID
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.graph_url}/media",
                params={
                    "access_token": token,
                    "image_url": media_url,
                    "caption": caption
                }
            ) as response:
                data = await response.json()
                return {"container_id": data["id"]}
    
    async def publish_media(self, token: str, container_id: str) -> Dict:
        """
        Publish media using container ID.
        
        Args:
            token: Access token
            container_id: Media container ID
            
        Returns:
            Dictionary containing post ID
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.graph_url}/media_publish",
                params={
                    "access_token": token,
                    "creation_id": container_id
                }
            ) as response:
                data = await response.json()
                return {"post_id": data["id"]}
    
    async def get_user_profile(self, token: str) -> Dict:
        """
        Get user profile information.
        
        Args:
            token: Access token
            
        Returns:
            Dictionary containing user profile data
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.graph_url}/me",
                params={
                    "access_token": token,
                    "fields": "id,username,account_type,media_count"
                }
            ) as response:
                return await response.json()
