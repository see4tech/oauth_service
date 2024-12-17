from typing import Dict, Optional, List
import aiohttp
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger

logger = get_logger(__name__)

class FacebookOAuth(OAuthBase):
    """Facebook OAuth 2.0 implementation."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="facebook")
        self.auth_url = "https://www.facebook.com/v12.0/dialog/oauth"
        self.token_url = "https://graph.facebook.com/v12.0/oauth/access_token"
        self.graph_url = "https://graph.facebook.com/v12.0"
        
        self.default_scope = [
            "public_profile",
            "email",
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_posts"
        ]
    
    async def get_authorization_url(self, state: Optional[str] = None,
                                  extra_scopes: Optional[List[str]] = None) -> str:
        """
        Get Facebook authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            extra_scopes: Additional OAuth scopes to request
            
        Returns:
            Authorization URL string
        """
        scopes = self.default_scope + (extra_scopes or [])
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "state": state,
            "scope": ",".join(scopes),
            "response_type": "code"
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
            async with session.get(
                self.token_url,
                params={
                    "client_id": self.client_id,
                    "client_secret": self.crypto.decrypt(self._client_secret),
                    "redirect_uri": self.callback_url,
                    "code": code
                }
            ) as response:
                data = await response.json()
                return {
                    "access_token": data["access_token"],
                    "token_type": "bearer",
                    "expires_in": data.get("expires_in", 3600)
                }
    
    async def refresh_token(self, access_token: str) -> Dict:
        """
        Refresh access token.
        
        Args:
            access_token: Current access token
            
        Returns:
            Dictionary containing new access token data
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.graph_url}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.client_id,
                    "client_secret": self.crypto.decrypt(self._client_secret),
                    "fb_exchange_token": access_token
                }
            ) as response:
                data = await response.json()
                return {
                    "access_token": data["access_token"],
                    "token_type": "bearer",
                    "expires_in": data.get("expires_in", 3600)
                }
    
    async def get_user_pages(self, token: str) -> List[Dict]:
        """
        Get list of pages managed by user.
        
        Args:
            token: Access token
            
        Returns:
            List of page information dictionaries
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.graph_url}/me/accounts",
                params={
                    "access_token": token,
                    "fields": "id,name,access_token"
                }
            ) as response:
                data = await response.json()
                return data.get("data", [])
    
    async def create_page_post(self, page_token: str, page_id: str,
                             content: Dict) -> Dict:
        """
        Create a post on a Facebook page.
        
        Args:
            page_token: Page access token
            page_id: ID of the page to post to
            content: Post content including text and media
            
        Returns:
            Dictionary containing post information
        """
        post_data = {
            "message": content.get("text", ""),
            "access_token": page_token
        }
        
        # Handle link attachment
        if content.get("link"):
            post_data["link"] = content["link"]
        
        # Handle media attachments
        if content.get("media_urls"):
            media_ids = await self._upload_media(
                page_token,
                page_id,
                content["media_urls"]
            )
            if media_ids:
                post_data["attached_media"] = [
                    {"media_fbid": media_id} for media_id in media_ids
                ]
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.graph_url}/{page_id}/feed",
                data=post_data
            ) as response:
                data = await response.json()
                return {"post_id": data["id"]}
    
    async def _upload_media(self, page_token: str, page_id: str,
                          media_urls: List[str]) -> List[str]:
        """
        Upload media files to Facebook.
        
        Args:
            page_token: Page access token
            page_id: ID of the page
            media_urls: List of media URLs to upload
            
        Returns:
            List of media IDs
        """
        media_ids = []
        
        async with aiohttp.ClientSession() as session:
            for url in media_urls:
                # First, create media container
                async with session.post(
                    f"{self.graph_url}/{page_id}/photos",
                    params={
                        "url": url,
                        "published": False,
                        "access_token": page_token
                    }
                ) as response:
                    data = await response.json()
                    media_ids.append(data["id"])
        
        return media_ids
