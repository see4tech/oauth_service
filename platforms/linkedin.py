from typing import Dict, Optional
import aiohttp
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger

logger = get_logger(__name__)

class LinkedInOAuth(OAuthBase):
    """LinkedIn OAuth 2.0 implementation."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="linkedin")
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.api_url = "https://api.linkedin.com/v2"
    
    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """Get LinkedIn authorization URL."""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "state": state,
            "scope": "r_liteprofile w_member_social"
        }
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        return f"{self.auth_url}?{query}"
    
    async def get_access_token(self, code: str) -> Dict:
        """Exchange authorization code for access token."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.crypto.decrypt(self._client_secret),
                    "redirect_uri": self.callback_url
                }
            ) as response:
                data = await response.json()
                return {
                    "access_token": data["access_token"],
                    "expires_in": data["expires_in"],
                    "refresh_token": data.get("refresh_token")
                }
    
    async def refresh_token(self, refresh_token: str) -> Dict:
        """Refresh access token."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.crypto.decrypt(self._client_secret)
                }
            ) as response:
                data = await response.json()
                return {
                    "access_token": data["access_token"],
                    "expires_in": data["expires_in"],
                    "refresh_token": data.get("refresh_token")
                }
    
    async def create_post(self, token: str, content: Dict) -> Dict:
        """Create a LinkedIn post."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        post_data = {
            "author": "urn:li:person:{person_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": content["text"]
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_url}/ugcPosts",
                headers=headers,
                json=post_data
            ) as response:
                data = await response.json()
                return {
                    "post_id": data["id"],
                    "status": "published"
                }
