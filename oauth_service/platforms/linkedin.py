from typing import Dict, Optional, List
import aiohttp
from fastapi import HTTPException
import json
import base64
from urllib.parse import urlencode
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger

logger = get_logger(__name__)

class LinkedInOAuth(OAuthBase):
    """LinkedIn OAuth 2.0 implementation."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="linkedin")
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.api_url = "https://api.linkedin.com/v2"
        
        # For LinkedIn, we need to use the exact registered callback URL
        # Remove any version suffix as it's not part of the registered URL
        self.callback_url = callback_url.replace('/2', '')
        
        logger.debug(f"Initialized LinkedIn OAuth with callback URL: {self.callback_url}")
        
        self.default_scopes = [
            'openid',
            'profile',
            'w_member_social',
            'email'
        ]
    
    async def get_authorization_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None) -> str:
        """Get LinkedIn authorization URL."""
        try:
            # Use provided scopes or default scopes
            final_scopes = scopes or self.default_scopes
            logger.debug(f"Building authorization URL with scopes: {' '.join(final_scopes)}")
            
            # Build authorization parameters
            params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.callback_url,  # Now includes /2
                'state': state,
                'scope': ' '.join(final_scopes)
            }
            
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}
            
            logger.debug(f"Authorization parameters: {params}")
            
            # Build URL with parameters
            query = urlencode(params)
            authorization_url = f"https://www.linkedin.com/oauth/v2/authorization?{query}"
            
            logger.debug(f"Generated authorization URL: {authorization_url}")
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error generating LinkedIn authorization URL: {str(e)}")
            raise

    async def get_access_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.
        """
        try:
            logger.debug(f"Exchanging code for access token. Code: {code[:10]}...")
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.crypto.decrypt(self._client_secret),
                "redirect_uri": self.callback_url
            }
            
            debug_data = dict(data)
            debug_data['client_secret'] = '[REDACTED]'
            logger.debug(f"Request data (excluding secret): {debug_data}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    data=data,
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json'
                    }
                ) as response:
                    logger.debug(f"Token response status: {response.status}")
                    response_text = await response.text()
                    logger.debug(f"Token response text: {response_text}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"LinkedIn token exchange failed: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return {
                        "access_token": data["access_token"],
                        "expires_in": data.get("expires_in", 3600),
                        "refresh_token": data.get("refresh_token")
                    }
                    
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error exchanging code for token: {str(e)}"
            )
    
    async def refresh_token(self, refresh_token: str) -> Dict:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token from previous authorization
            
        Returns:
            Dictionary containing new access token data
        """
        try:
            logger.debug("Attempting to refresh LinkedIn access token")
            
            auth_str = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
            auth_header = base64.b64encode(auth_str.encode()).decode()
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    data=urlencode(data),
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                        'Authorization': f'Basic {auth_header}'
                    }
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Refresh token response status: {response.status}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Token refresh failed: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return {
                        "access_token": data["access_token"],
                        "expires_in": data.get("expires_in", 3600),
                        "refresh_token": data.get("refresh_token")
                    }
                    
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error refreshing token: {str(e)}"
            )

    async def get_user_profile(self, token: str) -> str:
        """Get LinkedIn user profile to obtain member ID."""
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.linkedin.com/v2/userinfo",
                    headers=headers
                ) as response:
                    logger.debug(f"Profile request status: {response.status}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail="Failed to get user profile"
                        )
                    
                    data = json.loads(await response.text())
                    member_id = data.get('sub')
                    if not member_id:
                        raise HTTPException(
                            status_code=500,
                            detail="Member ID not found in profile response"
                        )
                    return member_id.replace('urn:li:person:', '')
                    
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting user profile: {str(e)}"
            )

    async def download_image(self, image_url: str) -> bytes:
        """Download image from URL and return binary data."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to download image: {await response.text()}"
                        )
                    return await response.read()
        except Exception as e:
            logger.error(f"Error downloading image: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error downloading image: {str(e)}"
            )
    async def register_upload(self, token: str, image_url: str) -> Dict:
        """Register an image upload with LinkedIn."""
        try:
            # First download the image
            image_data = await self.download_image(image_url)
            
            # Get member ID for ownership
            member_id = await self.get_user_profile(token)
            logger.debug("Retrieved member ID for upload")
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            register_data = {
                "registerUploadRequest": {
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "owner": f"urn:li:person:{member_id}",
                    "serviceRelationships": [{
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent"
                    }]
                }
            }
            
            logger.debug("Registering upload")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/assets?action=registerUpload",
                    headers=headers,
                    json=register_data
                ) as response:
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail="Failed to register upload"
                        )
                    
                    data = json.loads(await response.text())
                    logger.debug("Upload registered successfully")
                    
                    # Get upload URL and asset ID
                    upload_url = data["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                    asset = data["value"]["asset"]
                    
                    # Upload the image
                    await self.upload_image(upload_url, image_data)
                    
                    return {
                        "value": {
                            "asset": asset
                        }
                    }
                    
        except Exception as e:
            logger.error(f"Error registering upload: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error registering upload: {str(e)}"
            )

    async def upload_image(self, upload_url: str, image_data: bytes) -> None:
        """Upload image binary data to LinkedIn."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    upload_url,
                    data=image_data,
                    headers={
                        "Content-Type": "application/octet-stream"
                    }
                ) as response:
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to upload image: {await response.text()}"
                        )
        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error uploading image: {str(e)}"
            )

    async def create_post(self, token_data: Dict, content: Dict) -> Dict:
        """
        Create a LinkedIn post.
        
        Args:
            token_data: Dictionary containing access token
            content: Dictionary containing post content
            
        Returns:
            Dictionary containing post ID and URL
        """
        try:
            logger.debug("Starting LinkedIn post creation")
            
            # Get access token from token data
            access_token = token_data.get("access_token")
            if not access_token:
                logger.error("No access token found in token data")
                raise ValueError("No access token provided")
            
            # Get member ID for the post
            member_id = await self.get_user_profile(access_token)
            
            # Prepare post data
            post_data = {
                "author": f"urn:li:person:{member_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content.get("text", "")
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            # Handle media if provided
            if content.get("image_url"):
                logger.debug("Processing image upload")
                media_asset = await self.register_upload(access_token, content["image_url"])
                logger.debug("Media upload completed")
                
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"].update({
                    "shareMediaCategory": "IMAGE",
                    "media": [{
                        "status": "READY",
                        "description": {
                            "text": "Image"
                        },
                        "media": media_asset["value"]["asset"],
                        "title": {
                            "text": "Image"
                        }
                    }]
                })
            
            logger.debug("Creating post")
            
            # Create the post
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/ugcPosts",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "X-Restli-Protocol-Version": "2.0.0",
                        "Content-Type": "application/json"
                    },
                    json=post_data
                ) as response:
                    if not response.ok:
                        raise ValueError("Failed to create post")
                    
                    data = json.loads(await response.text())
                    post_id = data["id"]
                    logger.debug("Post created successfully")
                    
                    return {
                        "post_id": post_id,
                        "url": f"https://www.linkedin.com/feed/update/{post_id}"
                    }
                    
        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            raise