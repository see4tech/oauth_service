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
        # Use Facebook OAuth endpoints for Instagram Business
        self.auth_url = "https://www.facebook.com/v17.0/dialog/oauth"
        self.token_url = "https://graph.facebook.com/v17.0/oauth/access_token"
        self.graph_url = "https://graph.facebook.com/v17.0"  # Facebook Graph API
        self.ig_graph_url = "https://graph.instagram.com/v17.0"  # Instagram Graph API
    
    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get Facebook authorization URL for Instagram Business.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL string
        """
        # Instagram Business requires these specific scopes
        scopes = [
            "instagram_basic",            # Basic Instagram account info
            "instagram_content_publish",   # Ability to publish content
            "pages_show_list",            # To see connected Facebook Pages
            "pages_read_engagement",       # To read Instagram Business Account info
            "business_management"          # To manage Instagram Business Account
        ]
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.callback_url,
            "scope": ",".join(scopes),
            "response_type": "code",
            "state": state
        }
        query = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        return f"{self.auth_url}?{query}"
    
    async def get_access_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.
        This is a multi-step process for Instagram Business:
        1. Exchange code for Facebook access token
        2. Get connected Instagram Business account
        3. Get long-lived access token
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Dictionary containing access token and related data
        """
        try:
            async with aiohttp.ClientSession() as session:
                # Step 1: Exchange code for Facebook access token
                async with session.get(
                    self.token_url,
                    params={
                        "client_id": self.client_id,
                        "client_secret": self.crypto.decrypt(self._client_secret),
                        "redirect_uri": self.callback_url,
                        "code": code
                    }
                ) as response:
                    fb_token_data = await response.json()
                    if 'error' in fb_token_data:
                        raise ValueError(f"Failed to get Facebook token: {fb_token_data['error'].get('message')}")
                    
                    fb_access_token = fb_token_data["access_token"]
                    
                    # Step 2: Get connected Instagram Business account
                    async with session.get(
                        f"{self.graph_url}/me/accounts",
                        params={
                            "access_token": fb_access_token,
                            "fields": "instagram_business_account{id,username}"
                        }
                    ) as response:
                        pages_data = await response.json()
                        if 'error' in pages_data:
                            raise ValueError(f"Failed to get Instagram account: {pages_data['error'].get('message')}")
                        
                        # Find the page with an Instagram Business account
                        instagram_account = None
                        for page in pages_data.get('data', []):
                            if 'instagram_business_account' in page:
                                instagram_account = page['instagram_business_account']
                                break
                        
                        if not instagram_account:
                            raise ValueError("No Instagram Business account found")
                        
                        # Step 3: Get long-lived access token
                        async with session.get(
                            f"{self.graph_url}/oauth/access_token",
                            params={
                                "grant_type": "fb_exchange_token",
                                "client_id": self.client_id,
                                "client_secret": self.crypto.decrypt(self._client_secret),
                                "fb_exchange_token": fb_access_token
                            }
                        ) as response:
                            long_lived_data = await response.json()
                            if 'error' in long_lived_data:
                                raise ValueError(f"Failed to get long-lived token: {long_lived_data['error'].get('message')}")
                            
                            return {
                                "access_token": long_lived_data["access_token"],
                                "token_type": "bearer",
                                "expires_in": long_lived_data.get("expires_in", 5184000),  # 60 days default
                                "instagram_business_account_id": instagram_account["id"],
                                "instagram_username": instagram_account.get("username")
                            }
                            
        except Exception as e:
            logger.error(f"Error in Instagram OAuth flow: {str(e)}")
            raise

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
                f"{self.graph_url}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": self.client_id,
                    "client_secret": self.crypto.decrypt(self._client_secret),
                    "fb_exchange_token": access_token
                }
            ) as response:
                data = await response.json()
                if 'error' in data:
                    raise ValueError(f"Failed to refresh token: {data['error'].get('message')}")
                return {
                    "access_token": data["access_token"],
                    "token_type": "bearer",
                    "expires_in": data.get("expires_in", 5184000)  # 60 days default
                }
    
    async def create_media_container(self, token: str, media_url: str, caption: str) -> Dict:
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
                f"{self.ig_graph_url}/media",
                params={
                    "access_token": token,
                    "image_url": media_url,
                    "caption": caption,
                    "media_type": "IMAGE"
                }
            ) as response:
                data = await response.json()
                if 'error' in data:
                    raise ValueError(f"Failed to create media container: {data['error'].get('message')}")
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
                f"{self.ig_graph_url}/media_publish",
                params={
                    "access_token": token,
                    "creation_id": container_id
                }
            ) as response:
                data = await response.json()
                if 'error' in data:
                    raise ValueError(f"Failed to publish media: {data['error'].get('message')}")
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
                f"{self.ig_graph_url}/me",
                params={
                    "access_token": token,
                    "fields": "id,username,account_type,media_count"
                }
            ) as response:
                data = await response.json()
                if 'error' in data:
                    raise ValueError(f"Failed to get profile: {data['error'].get('message')}")
                return data
    
    async def create_post(self, token: str, content: Dict) -> Dict:
        """
        Create a post on Instagram.
        
        Args:
            token: Access token
            content: Dictionary containing post content (text and image_url)
            
        Returns:
            Dictionary containing post information
        """
        if not content.get("image_url"):
            raise ValueError("Instagram requires an image for posting")

        try:
            # First create a media container
            container = await self.create_media_container(
                token=token,
                media_url=content["image_url"],
                caption=content["text"]
            )
            
            # Then publish the media
            result = await self.publish_media(
                token=token,
                container_id=container["container_id"]
            )
            
            return {
                "post_id": result["post_id"],
                "platform": "instagram",
                "url": f"https://instagram.com/p/{result['post_id']}"
            }
            
        except Exception as e:
            logger.error(f"Error creating Instagram post: {str(e)}")
            raise
