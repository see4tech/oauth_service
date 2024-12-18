# from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request
# from typing import Optional, Dict, List
# from pydantic import BaseModel
# from ..core import TokenManager
# from ..platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth
# from ..models.oauth_models import (
#     OAuthInitRequest, OAuthInitResponse, OAuthCallbackRequest,
#     TokenResponse, PostContent, PostResponse, MediaUploadResponse, UserProfile
# )
# from ..utils.logger import get_logger
# from ..config import get_settings
# from fastapi.responses import RedirectResponse
# import json

# logger = get_logger(__name__)
# router = APIRouter()
# settings = get_settings()

# # Request models
# class SimplePostRequest(BaseModel):
#     user_id: str
#     content: Dict[str, str]

# class MediaUploadRequest(BaseModel):
#     user_id: str

# class ProfileRequest(BaseModel):
#     user_id: str

# class RefreshTokenRequest(BaseModel):
#     user_id: str

# async def get_oauth_handler(platform: str):
#     """
#     Get the appropriate OAuth handler for the specified platform.
    
#     Args:
#         platform (str): The platform identifier (twitter, linkedin, etc.)
        
#     Returns:
#         OAuthBase: An instance of the platform-specific OAuth handler
        
#     Raises:
#         HTTPException: If platform is unsupported or credentials are invalid
#     """
#     handlers = {
#         "twitter": TwitterOAuth,
#         "linkedin": LinkedInOAuth,
#         "instagram": InstagramOAuth,
#         "facebook": FacebookOAuth
#     }
    
#     if platform not in handlers:
#         raise HTTPException(
#             status_code=400, 
#             detail=f"Unsupported platform: {platform}"
#         )
    
#     try:
#         credentials = settings.get_platform_credentials(platform)
#         return handlers[platform](**credentials)
#     except ValueError as e:
#         logger.error(f"Error getting OAuth handler for {platform}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/{platform}/init", response_model=OAuthInitResponse)
# async def initialize_oauth(
#     platform: str, 
#     request: OAuthInitRequest
# ) -> OAuthInitResponse:
#     """
#     Initialize OAuth flow for the specified platform.
    
#     Args:
#         platform (str): The platform to authenticate with
#         request (OAuthInitRequest): The initialization request data
        
#     Returns:
#         OAuthInitResponse: Contains authorization URL and state
        
#     Raises:
#         HTTPException: If initialization fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
        
#         state = oauth_handler.generate_state(
#             user_id=request.user_id,
#             frontend_callback_url=str(request.frontend_callback_url)
#         )
        
#         auth_url = await oauth_handler.get_authorization_url(
#             state=state,
#             scopes=request.scopes
#         )
        
#         if isinstance(auth_url, dict):
#             return OAuthInitResponse(
#                 authorization_url=auth_url.get('oauth2_url'),
#                 state=state,
#                 platform=platform,
#                 additional_params={"oauth1_url": auth_url.get('oauth1_url')}
#             )
        
#         return OAuthInitResponse(
#             authorization_url=auth_url,
#             state=state,
#             platform=platform
#         )
        
#     except Exception as e:
#         logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/{platform}/token", response_model=TokenResponse)
# async def exchange_code(
#     platform: str,
#     request: OAuthCallbackRequest
# ) -> TokenResponse:
#     """
#     Exchange authorization code for access token.
    
#     Args:
#         platform (str): The platform identifier
#         request (OAuthCallbackRequest): The callback request data
        
#     Returns:
#         TokenResponse: Contains access token and related data
        
#     Raises:
#         HTTPException: If token exchange fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
        
#         state_data = oauth_handler.verify_state(request.state)
#         if not state_data:
#             raise HTTPException(
#                 status_code=400, 
#                 detail="Invalid state parameter"
#             )
            
#         token_data = await oauth_handler.get_access_token(request.code)
        
#         token_manager = TokenManager()
#         await token_manager.store_token(
#             platform=platform,
#             user_id=state_data['user_id'],
#             token_data=token_data
#         )
        
#         return TokenResponse(
#             access_token=token_data["access_token"],
#             token_type=token_data.get("token_type", "Bearer"),
#             expires_in=token_data.get("expires_in", 3600),
#             refresh_token=token_data.get("refresh_token"),
#             scope=token_data.get("scope"),
#         )
        
#     except Exception as e:
#         logger.error(f"Error exchanging code for tokens: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/{platform}/refresh", response_model=TokenResponse)
# async def refresh_token(
#     platform: str,
#     request: RefreshTokenRequest
# ) -> TokenResponse:
#     """
#     Refresh an expired access token.
    
#     Args:
#         platform (str): The platform identifier
#         request (RefreshTokenRequest): Contains user_id
        
#     Returns:
#         TokenResponse: Contains new access token and related data
        
#     Raises:
#         HTTPException: If token refresh fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         token_data = await token_manager.get_valid_token(platform, request.user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         new_token_data = await oauth_handler.refresh_token(
#             token_data.get("refresh_token")
#         )
        
#         await token_manager.store_token(platform, request.user_id, new_token_data)
        
#         return TokenResponse(
#             access_token=new_token_data["access_token"],
#             token_type=new_token_data.get("token_type", "Bearer"),
#             expires_in=new_token_data.get("expires_in", 3600),
#             refresh_token=new_token_data.get("refresh_token"),
#             scope=new_token_data.get("scope"),
#         )
        
#     except Exception as e:
#         logger.error(f"Error refreshing token for {platform}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))

# @router.post("/{platform}/post", response_model=PostResponse)
# async def create_post(
#     platform: str,
#     request: SimplePostRequest,
# ) -> PostResponse:
#     """
#     Create a post on the specified platform.
    
#     Args:
#         platform (str): The platform to post to
#         request (SimplePostRequest): Contains user_id and post content
        
#     Returns:
#         PostResponse: Contains post ID and related data
        
#     Raises:
#         HTTPException: If posting fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         token_data = await token_manager.get_valid_token(platform, request.user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found for this user"
#             )
        
#         result = await oauth_handler.create_post(
#             token_data["access_token"],
#             request.content
#         )
        
#         return PostResponse(
#             post_id=result["post_id"],
#             platform=platform,
#             url=result.get("url"),
#             platform_specific_data=result.get("additional_data")
#         )
        
#     except Exception as e:
#         logger.error(f"Error creating post on {platform}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))
# @router.post("/{platform}/media/upload", response_model=MediaUploadResponse)
# async def upload_media(
#     platform: str,
#     file: UploadFile = File(...),
#     request: MediaUploadRequest = None,
# ) -> MediaUploadResponse:
#     """
#     Upload media to the specified platform.
    
#     Args:
#         platform (str): The platform to upload to
#         file (UploadFile): The media file to upload
#         request (MediaUploadRequest): Contains user_id
        
#     Returns:
#         MediaUploadResponse: Contains media ID and URLs
        
#     Raises:
#         HTTPException: If upload fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         token_data = await token_manager.get_valid_token(platform, request.user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         content = await file.read()
        
#         result = await oauth_handler.upload_media(
#             token_data["access_token"],
#             content,
#             file.filename
#         )
        
#         return MediaUploadResponse(
#             media_id=result["media_id"],
#             media_type=file.content_type,
#             url=result.get("url"),
#             thumbnail_url=result.get("thumbnail_url")
#         )
        
#     except Exception as e:
#         logger.error(f"Error uploading media to {platform}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))


# @router.post("/{platform}/profile", response_model=UserProfile)
# async def get_profile(
#     platform: str,
#     request: ProfileRequest,
# ) -> UserProfile:
#     """
#     Get user profile from the specified platform.
    
#     Args:
#         platform (str): The platform to get profile from
#         request (ProfileRequest): Contains user_id
        
#     Returns:
#         UserProfile: Contains user profile data
        
#     Raises:
#         HTTPException: If profile retrieval fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         token_data = await token_manager.get_valid_token(platform, request.user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         profile_data = await oauth_handler.get_profile(
#             token_data["access_token"]
#         )
        
#         return UserProfile(
#             id=profile_data["id"],
#             platform=platform,
#             username=profile_data.get("username"),
#             name=profile_data.get("name"),
#             email=profile_data.get("email"),
#             profile_url=profile_data.get("profile_url"),
#             avatar_url=profile_data.get("avatar_url"),
#             raw_data=profile_data
#         )
        
#     except Exception as e:
#         logger.error(f"Error getting profile from {platform}: {str(e)}")
#         raise HTTPException(status_code=500, detail=str(e))
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
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="linkedin")
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.api_url = "https://api.linkedin.com/v2"
        logger.debug(f"Initialized LinkedIn OAuth with callback URL: {callback_url}")
    
    async def get_authorization_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None) -> str:
        try:
            scope_str = " ".join(scopes) if scopes else "openid profile w_member_social email"
            
            params = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.callback_url,
                "state": state,
                "scope": scope_str
            }
            
            logger.debug(f"Building authorization URL with scopes: {scope_str}")
            logger.debug(f"Authorization parameters: {params}")
            
            query = urlencode(params)
            auth_url = f"{self.auth_url}?{query}"
            
            logger.debug(f"Generated authorization URL: {auth_url}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating authorization URL: {str(e)}"
            )

    async def get_access_token(self, code: str) -> Dict:
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
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Accept": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_url}/me",
                    headers=headers
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Profile response status: {response.status}")
                    logger.debug(f"Profile response: {response_text}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to get user profile: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    member_id = data.get('id')
                    if not member_id:
                        raise HTTPException(
                            status_code=500,
                            detail="Member ID not found in profile response"
                        )
                    return member_id
                    
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error getting user profile: {str(e)}"
            )

    async def download_image(self, image_url: str) -> bytes:
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

    async def register_upload(self, token: str, member_id: str) -> Dict:
        try:
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
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/assets?action=registerUpload",
                    headers=headers,
                    json=register_data
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Register upload response: {response_text}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to register upload: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return data["value"]["asset"]
                    
        except Exception as e:
            logger.error(f"Error registering upload: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error registering upload: {str(e)}"
            )

    async def upload_image(self, upload_url: str, image_data: bytes) -> None:
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

    async def create_post(self, token: str, content: Dict) -> Dict:
        try:
            member_id = await self.get_user_profile(token)
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            post_data = {
                "author": f"urn:li:person:{member_id}",
                "lifecycleState": "PUBLISHED",
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }

            if image_url := content.get("image_url"):
                image_data = await self.download_image(image_url)
                register_data = await self.register_upload(token, member_id)
                upload_url = register_data["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
                asset_id = register_data["id"]
                
                await self.upload_image(upload_url, image_data)
                
                post_data["specificContent"] = {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content.get("text", "")
                        },
                        "shareMediaCategory": "IMAGE",
                        "media": [{
                            "status": "READY",
                            "media": asset_id
                        }]
                    }
                }
            else:
                post_data["specificContent"] = {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content.get("text", "")
                        },
                        "shareMediaCategory": "NONE"
                    }
                }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/ugcPosts",
                    headers=headers,
                    json=post_data
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Post creation response: {response_text}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to create post: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return {
                        "post_id": data["id"],
                        "status": "published",
                        "platform": "linkedin"
                    }
                    
        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating post: {str(e)}"
            )