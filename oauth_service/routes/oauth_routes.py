# from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request
# from typing import Optional, Dict, List
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
        
#         # Generate state with user ID and callback URL
#         state = oauth_handler.generate_state(
#             user_id=request.user_id,
#             frontend_callback_url=str(request.frontend_callback_url)
#         )
        
#         # Get authorization URL with scopes
#         auth_url = await oauth_handler.get_authorization_url(
#             state=state,
#             scopes=request.scopes
#         )
        
#         # Handle platforms that return multiple URLs (like Twitter)
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
        
#         # Verify the state matches
#         state_data = oauth_handler.verify_state(request.state)
#         if not state_data:
#             raise HTTPException(
#                 status_code=400, 
#                 detail="Invalid state parameter"
#             )
            
#         # Exchange the code for tokens
#         token_data = await oauth_handler.get_access_token(request.code)
        
#         # Store the tokens
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
#     user_id: str,
#     authorization: str = Header(...)
# ) -> TokenResponse:
#     """
#     Refresh an expired access token.
    
#     Args:
#         platform (str): The platform identifier
#         user_id (str): The user's ID
#         authorization (str): Bearer token
        
#     Returns:
#         TokenResponse: Contains new access token and related data
        
#     Raises:
#         HTTPException: If token refresh fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         # Get existing token data
#         token_data = await token_manager.get_valid_token(platform, user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         # Refresh the token
#         new_token_data = await oauth_handler.refresh_token(
#             token_data.get("refresh_token")
#         )
        
#         # Store the new tokens
#         await token_manager.store_token(platform, user_id, new_token_data)
        
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
#     content: PostContent,
#     user_id: str,
#     authorization: str = Header(...)
# ) -> PostResponse:
#     """
#     Create a post on the specified platform.
    
#     Args:
#         platform (str): The platform to post to
#         content (PostContent): The content to post
#         user_id (str): The user's ID
#         authorization (str): Bearer token
        
#     Returns:
#         PostResponse: Contains post ID and related data
        
#     Raises:
#         HTTPException: If posting fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         # Get valid token
#         token_data = await token_manager.get_valid_token(platform, user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         # Create the post
#         result = await oauth_handler.create_post(
#             token_data["access_token"],
#             content.dict()
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
#     user_id: str = None,
#     authorization: str = Header(...)
# ) -> MediaUploadResponse:
#     """
#     Upload media to the specified platform.
    
#     Args:
#         platform (str): The platform to upload to
#         file (UploadFile): The media file to upload
#         user_id (str): The user's ID
#         authorization (str): Bearer token
        
#     Returns:
#         MediaUploadResponse: Contains media ID and URLs
        
#     Raises:
#         HTTPException: If upload fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         # Get valid token
#         token_data = await token_manager.get_valid_token(platform, user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         # Read file content
#         content = await file.read()
        
#         # Upload media
#         result = await oauth_handler.upload_media(
#             token_data,
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

# @router.get("/{platform}/profile", response_model=UserProfile)
# async def get_profile(
#     platform: str,
#     user_id: str,
#     authorization: str = Header(...)
# ) -> UserProfile:
#     """
#     Get user profile from the specified platform.
    
#     Args:
#         platform (str): The platform to get profile from
#         user_id (str): The user's ID
#         authorization (str): Bearer token
        
#     Returns:
#         UserProfile: Contains user profile data
        
#     Raises:
#         HTTPException: If profile retrieval fails
#     """
#     try:
#         oauth_handler = await get_oauth_handler(platform)
#         token_manager = TokenManager()
        
#         # Get valid token
#         token_data = await token_manager.get_valid_token(platform, user_id)
#         if not token_data:
#             raise HTTPException(
#                 status_code=401,
#                 detail="No valid token found"
#             )
        
#         # Get profile data
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
from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request
from typing import Optional, Dict, List
from pydantic import BaseModel
from ..core import TokenManager
from ..platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth
from ..models.oauth_models import (
    OAuthInitRequest, OAuthInitResponse, OAuthCallbackRequest,
    TokenResponse, PostContent, PostResponse, MediaUploadResponse, UserProfile
)
from ..utils.logger import get_logger
from ..config import get_settings
from fastapi.responses import RedirectResponse
import json

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

# Add new model for the simplified post request
class SimplePostRequest(BaseModel):
    user_id: str
    content: Dict[str, str]

async def get_oauth_handler(platform: str):
    """
    Get the appropriate OAuth handler for the specified platform.
    
    Args:
        platform (str): The platform identifier (twitter, linkedin, etc.)
        
    Returns:
        OAuthBase: An instance of the platform-specific OAuth handler
        
    Raises:
        HTTPException: If platform is unsupported or credentials are invalid
    """
    handlers = {
        "twitter": TwitterOAuth,
        "linkedin": LinkedInOAuth,
        "instagram": InstagramOAuth,
        "facebook": FacebookOAuth
    }
    
    if platform not in handlers:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported platform: {platform}"
        )
    
    try:
        credentials = settings.get_platform_credentials(platform)
        return handlers[platform](**credentials)
    except ValueError as e:
        logger.error(f"Error getting OAuth handler for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/init", response_model=OAuthInitResponse)
async def initialize_oauth(
    platform: str, 
    request: OAuthInitRequest
) -> OAuthInitResponse:
    """
    Initialize OAuth flow for the specified platform.
    
    Args:
        platform (str): The platform to authenticate with
        request (OAuthInitRequest): The initialization request data
        
    Returns:
        OAuthInitResponse: Contains authorization URL and state
        
    Raises:
        HTTPException: If initialization fails
    """
    try:
        oauth_handler = await get_oauth_handler(platform)
        
        # Generate state with user ID and callback URL
        state = oauth_handler.generate_state(
            user_id=request.user_id,
            frontend_callback_url=str(request.frontend_callback_url)
        )
        
        # Get authorization URL with scopes
        auth_url = await oauth_handler.get_authorization_url(
            state=state,
            scopes=request.scopes
        )
        
        # Handle platforms that return multiple URLs (like Twitter)
        if isinstance(auth_url, dict):
            return OAuthInitResponse(
                authorization_url=auth_url.get('oauth2_url'),
                state=state,
                platform=platform,
                additional_params={"oauth1_url": auth_url.get('oauth1_url')}
            )
        
        return OAuthInitResponse(
            authorization_url=auth_url,
            state=state,
            platform=platform
        )
        
    except Exception as e:
        logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/token", response_model=TokenResponse)
async def exchange_code(
    platform: str,
    request: OAuthCallbackRequest
) -> TokenResponse:
    """
    Exchange authorization code for access token.
    
    Args:
        platform (str): The platform identifier
        request (OAuthCallbackRequest): The callback request data
        
    Returns:
        TokenResponse: Contains access token and related data
        
    Raises:
        HTTPException: If token exchange fails
    """
    try:
        oauth_handler = await get_oauth_handler(platform)
        
        # Verify the state matches
        state_data = oauth_handler.verify_state(request.state)
        if not state_data:
            raise HTTPException(
                status_code=400, 
                detail="Invalid state parameter"
            )
            
        # Exchange the code for tokens
        token_data = await oauth_handler.get_access_token(request.code)
        
        # Store the tokens
        token_manager = TokenManager()
        await token_manager.store_token(
            platform=platform,
            user_id=state_data['user_id'],
            token_data=token_data
        )
        
        return TokenResponse(
            access_token=token_data["access_token"],
            token_type=token_data.get("token_type", "Bearer"),
            expires_in=token_data.get("expires_in", 3600),
            refresh_token=token_data.get("refresh_token"),
            scope=token_data.get("scope"),
        )
        
    except Exception as e:
        logger.error(f"Error exchanging code for tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/refresh", response_model=TokenResponse)
async def refresh_token(
    platform: str,
    user_id: str,
    authorization: str = Header(...)
) -> TokenResponse:
    """
    Refresh an expired access token.
    
    Args:
        platform (str): The platform identifier
        user_id (str): The user's ID
        authorization (str): Bearer token
        
    Returns:
        TokenResponse: Contains new access token and related data
        
    Raises:
        HTTPException: If token refresh fails
    """
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        # Get existing token data
        token_data = await token_manager.get_valid_token(platform, user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
        # Refresh the token
        new_token_data = await oauth_handler.refresh_token(
            token_data.get("refresh_token")
        )
        
        # Store the new tokens
        await token_manager.store_token(platform, user_id, new_token_data)
        
        return TokenResponse(
            access_token=new_token_data["access_token"],
            token_type=new_token_data.get("token_type", "Bearer"),
            expires_in=new_token_data.get("expires_in", 3600),
            refresh_token=new_token_data.get("refresh_token"),
            scope=new_token_data.get("scope"),
        )
        
    except Exception as e:
        logger.error(f"Error refreshing token for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/post", response_model=PostResponse)
async def create_post(
    platform: str,
    request: SimplePostRequest,
) -> PostResponse:
    """
    Create a post on the specified platform.
    
    Args:
        platform (str): The platform to post to
        request (SimplePostRequest): Contains user_id and post content
        
    Returns:
        PostResponse: Contains post ID and related data
        
    Raises:
        HTTPException: If posting fails
    """
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        # Get valid token using user_id from request
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_,
                detail="No valid token found for this user"
            )
        
        # Create the post using the stored token
        result = await oauth_handler.create_post(
            token_data["access_token"],
            request.content
        )
        
        return PostResponse(
            post_id=result["post_id"],
            platform=platform,
            url=result.get("url"),
            platform_specific_data=result.get("additional_data")
        )
        
    except Exception as e:
        logger.error(f"Error creating post on {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/media/upload", response_model=MediaUploadResponse)
async def upload_media(
    platform: str,
    file: UploadFile = File(...),
    user_id: str = None,
    authorization: str = Header(...)
) -> MediaUploadResponse:
    """
    Upload media to the specified platform.
    
    Args:
        platform (str): The platform to upload to
        file (UploadFile): The media file to upload
        user_id (str): The user's ID
        authorization (str): Bearer token
        
    Returns:
        MediaUploadResponse: Contains media ID and URLs
        
    Raises:
        HTTPException: If upload fails
    """
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        # Get valid token
        token_data = await token_manager.get_valid_token(platform, user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
        # Read file content
        content = await file.read()
        
        # Upload media
        result = await oauth_handler.upload_media(
            token_data,
            content,
            file.filename
        )
        
        return MediaUploadResponse(
            media_id=result["media_id"],
            media_type=file.content_type,
            url=result.get("url"),
            thumbnail_url=result.get("thumbnail_url")
        )
        
    except Exception as e:
        logger.error(f"Error uploading media to {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{platform}/profile", response_model=UserProfile)
async def get_profile(
    platform: str,
    user_id: str,
    authorization: str = Header(...)
) -> UserProfile:
    """
    Get user profile from the specified platform.
    
    Args:
        platform (str): The platform to get profile from
        user_id (str): The user's ID
        authorization (str): Bearer token
        
    Returns:
        UserProfile: Contains user profile data
        
    Raises:
        HTTPException: If profile retrieval fails
    """
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        # Get valid token
        token_data = await token_manager.get_valid_token(platform, user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
        # Get profile data
        profile_data = await oauth_handler.get_profile(
            token_data["access_token"]
        )
        
        return UserProfile(
            id=profile_data["id"],
            platform=platform,
            username=profile_data.get("username"),
            name=profile_data.get("name"),
            email=profile_data.get("email"),
            profile_url=profile_data.get("profile_url"),
            avatar_url=profile_data.get("avatar_url"),
            raw_data=profile_data
        )
        
    except Exception as e:
        logger.error(f"Error getting profile from {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))