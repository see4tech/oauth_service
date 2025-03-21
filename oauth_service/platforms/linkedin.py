from typing import Dict, Optional, List, Any
import aiohttp
from fastapi import HTTPException
import json
import base64
from urllib.parse import urlencode
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger
from ..core.token_refresh_handler import refresh_handler
import datetime
import asyncio

logger = get_logger(__name__)

class LinkedInOAuth(OAuthBase):
    """LinkedIn OAuth 2.0 implementation."""
    
    # Class-level rate limiters
    _token_exchange_limiter = None
    _api_limiter = None

    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        
        # Initialize rate limiters only if not already initialized
        if LinkedInOAuth._token_exchange_limiter is None:
            LinkedInOAuth._token_exchange_limiter = RateLimiter(platform="linkedin_token_exchange")
            logger.debug("Initialized class-level token exchange rate limiter")
        if LinkedInOAuth._api_limiter is None:
            LinkedInOAuth._api_limiter = RateLimiter(platform="linkedin")
            logger.debug("Initialized class-level API rate limiter")
        
        # Use class-level rate limiters
        self.token_exchange_limiter = LinkedInOAuth._token_exchange_limiter
        self.api_limiter = LinkedInOAuth._api_limiter
        
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
            'email',
            'offline_access'  # Required for refresh tokens
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

    async def get_access_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        logger.debug(f"Exchanging code for access token. Code: {code[:10]}...")
        
        try:
            # Wait for token exchange rate limit
            await self.token_exchange_limiter.wait("token_exchange")
            logger.debug("Token exchange rate limit check passed, proceeding with exchange")
            
            # Log timestamp for rate limit tracking
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.debug(f"\n=== LinkedIn Token Request Timestamp ===")
            logger.debug(f"Request Time: {current_time}")
            
            # Prepare token exchange data
            data = {
                'grant_type': 'authorization_code',
                'code': code,
                'client_id': self.client_id,
                'client_secret': self.crypto.decrypt(self._client_secret),
                'redirect_uri': self.callback_url
            }
            
            # Log request details (excluding secret)
            safe_data = data.copy()
            safe_data['client_secret'] = '[REDACTED]'
            logger.debug(f"Request data (excluding secret): {safe_data}")
            
            # Create Basic Auth header
            auth_str = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
            auth_header = base64.b64encode(auth_str.encode()).decode()
            
            logger.debug("\n=== LinkedIn Token Exchange Request ===")
            logger.debug(f"Token URL: {self.token_url}")
            logger.debug(f"Client ID length: {len(self.client_id)}")
            logger.debug(f"Auth header length: {len(auth_header)}")
            logger.debug(f"Redirect URI: {self.callback_url}")
            
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
                    logger.debug(f"Token response status: {response.status}")
                    logger.debug(f"Token response headers: {dict(response.headers)}")
                    logger.debug(f"Token response text: {response_text if response_text else '(empty response)'}")
                    
                    if response.status == 429:
                        # Reset token exchange rate limiter on 429
                        await self.token_exchange_limiter.reset("token_exchange")
                        logger.error("\n=== LinkedIn Rate Limit Error ===")
                        logger.error(f"Rate limit headers: {dict(response.headers)}")
                        
                        # Log request timing details
                        response_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        logger.error(f"\n=== Request Timing ===")
                        logger.error(f"Request started at: {current_time}")
                        logger.error(f"Response received at: {response_time}")
                        
                        # Log LinkedIn-specific headers
                        logger.error("\n=== LinkedIn Response Details ===")
                        logger.error(f"X-Li-Fabric: {response.headers.get('X-Li-Fabric')}")
                        logger.error(f"X-Li-Pop: {response.headers.get('X-Li-Pop')}")
                        logger.error(f"X-Li-Proto: {response.headers.get('X-Li-Proto')}")
                        logger.error(f"X-LI-UUID: {response.headers.get('X-LI-UUID')}")
                        
                        error_msg = "LinkedIn rate limit exceeded. Please wait 60 seconds before initiating a new OAuth flow."
                        raise HTTPException(status_code=429, detail=error_msg)
                    
                    if not response.ok:
                        logger.error(f"\n=== LinkedIn Token Exchange Error ===")
                        logger.error(f"Status code: {response.status}")
                        logger.error(f"Response headers: {dict(response.headers)}")
                        logger.error(f"Error response: {response_text if response_text else '(empty response)'}")
                        
                        error_msg = f"LinkedIn token exchange failed"
                        if response_text:
                            try:
                                error_data = json.loads(response_text)
                                if 'error_description' in error_data:
                                    error_msg += f": {error_data['error_description']}"
                                elif 'error' in error_data:
                                    error_msg += f": {error_data['error']}"
                                else:
                                    error_msg += f": {response_text}"
                            except json.JSONDecodeError:
                                error_msg += f": {response_text}"
                        
                        raise HTTPException(
                            status_code=response.status,
                            detail=error_msg
                        )
                    
                    try:
                        token_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse token response as JSON: {response_text}")
                        raise HTTPException(
                            status_code=500,
                            detail="Invalid token response format from LinkedIn"
                        )
                    
                    logger.debug("\n=== LinkedIn Token Exchange Success ===")
                    logger.debug(f"Token data keys: {list(token_data.keys())}")
                    logger.debug(f"Expires in: {token_data.get('expires_in')} seconds")
                    logger.debug(f"Received refresh token: {bool(token_data.get('refresh_token'))}")
                    
                    # Calculate expires_at
                    expires_in = token_data.get('expires_in', 3600)
                    expires_at = int(datetime.datetime.utcnow().timestamp() + expires_in)
                    
                    return {
                        'access_token': token_data['access_token'],
                        'expires_in': expires_in,
                        'expires_at': expires_at,
                        'refresh_token': token_data.get('refresh_token')
                    }
                    
        except HTTPException:
            # Pass through HTTP exceptions without wrapping
            raise
        except Exception as e:
            # Wrap non-HTTP exceptions in 500
            logger.error(f"Unexpected error exchanging code for token: {str(e)}")
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
            logger.debug("\n=== LinkedIn Token Refresh Started ===")
            logger.debug(f"Refresh token provided (first 10 chars): {refresh_token[:10]}...")
            
            auth_str = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
            auth_header = base64.b64encode(auth_str.encode()).decode()
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.crypto.decrypt(self._client_secret)
            }
            
            logger.debug("\n=== LinkedIn Refresh Request Details ===")
            logger.debug(f"Token URL: {self.token_url}")
            logger.debug(f"Client ID length: {len(self.client_id)}")
            logger.debug(f"Auth header length: {len(auth_header)}")
            
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
                    logger.debug(f"\n=== LinkedIn Refresh Response ===")
                    logger.debug(f"Status code: {response.status}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                    
                    if not response.ok:
                        logger.error(f"\n=== LinkedIn Token Refresh Error ===")
                        logger.error(f"Status code: {response.status}")
                        logger.error(f"Response headers: {dict(response.headers)}")
                        logger.error(f"Error response: {response_text}")
                        raise ValueError(f"Failed to refresh token: {response_text}")
                    
                    try:
                        token_data = json.loads(response_text)
                    except json.JSONDecodeError:
                        logger.error(f"Failed to parse refresh response as JSON: {response_text}")
                        raise ValueError("Invalid token response format from LinkedIn")
                    
                    logger.debug("\n=== LinkedIn Token Refresh Success ===")
                    logger.debug(f"Token data keys: {list(token_data.keys())}")
                    logger.debug(f"Expires in: {token_data.get('expires_in')} seconds")
                    logger.debug(f"Received refresh token: {bool(token_data.get('refresh_token'))}")
                    
                    # Calculate expires_at
                    expires_in = token_data.get('expires_in', 3600)
                    expires_at = datetime.datetime.utcnow().timestamp() + expires_in
                    
                    return {
                        'access_token': token_data['access_token'],
                        'expires_in': expires_in,
                        'expires_at': expires_at,
                        'refresh_token': token_data.get('refresh_token', refresh_token)  # Use old refresh token if new one not provided
                    }
                    
        except Exception as e:
            logger.error(f"\n=== LinkedIn Token Refresh Error ===")
            logger.error(f"Error refreshing token: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise

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

    async def create_post(self, token_data: Dict, content: Dict, user_id: str = None, x_api_key: str = None) -> Dict:
        """
        Create a LinkedIn post.
        
        Args:
            token_data: Dictionary containing access token
            content: Dictionary containing post content
            user_id: Optional user identifier for token refresh
            x_api_key: Optional API key for token refresh
            
        Returns:
            Dictionary containing post ID and URL
        """
        try:
            logger.debug("Starting LinkedIn post creation")
            
            # Get fresh token data if user_id is provided
            if user_id:
                logger.debug(f"Checking token validity for user {user_id}")
                token_data = await refresh_handler.get_valid_token(user_id, "linkedin", x_api_key)
                if not token_data:
                    raise ValueError("Failed to get valid token")
            
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
                        error_text = await response.text()
                        # Sanitize error message in case it contains tokens
                        safe_error = error_text.replace(access_token, '[REDACTED]') if access_token in error_text else error_text
                        raise ValueError(f"Failed to create post: {safe_error}")
                    
                    data = json.loads(await response.text())
                    post_id = data["id"]
                    logger.debug("Post created successfully")
                    
                    return {
                        "post_id": post_id,
                        "url": f"https://www.linkedin.com/feed/update/{post_id}"
                    }
                    
        except Exception as e:
            # Ensure no tokens are logged in the error
            error_msg = str(e)
            if 'access_token' in locals() and access_token and access_token in error_msg:
                error_msg = error_msg.replace(access_token, '[REDACTED]')
            logger.error(f"Error creating post: {error_msg}")
            raise