from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
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

# Request models
class PostContent(BaseModel):
    text: str
    image_url: Optional[str] = None

class SimplePostRequest(BaseModel):
    user_id: str
    content: PostContent

class MediaUploadRequest(BaseModel):
    user_id: str

class ProfileRequest(BaseModel):
    user_id: str

class RefreshTokenRequest(BaseModel):
    user_id: str

async def get_oauth_handler(platform: str):
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
        
        # For Twitter, only pass OAuth 2.0 credentials during initialization
        if platform == "twitter":
            oauth_credentials = {
                "client_id": credentials["client_id"],
                "client_secret": credentials["client_secret"],
                "callback_url": credentials["callback_url"]
            }
        else:
            oauth_credentials = credentials
            
        return handlers[platform](**oauth_credentials)
    except ValueError as e:
        logger.error(f"Error getting OAuth handler for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/init", response_model=OAuthInitResponse)
async def initialize_oauth(
    platform: str, 
    request: OAuthInitRequest
) -> OAuthInitResponse:
    try:
        oauth_handler = await get_oauth_handler(platform)
        
        state = oauth_handler.generate_state(
            user_id=request.user_id,
            frontend_callback_url=str(request.frontend_callback_url)
        )
        
        auth_url = await oauth_handler.get_authorization_url(
            state=state,
            scopes=request.scopes
        )
        
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
    try:
        oauth_handler = await get_oauth_handler(platform)
        
        state_data = oauth_handler.verify_state(request.state)
        if not state_data:
            raise HTTPException(
                status_code=400, 
                detail="Invalid state parameter"
            )
            
        token_data = await oauth_handler.get_access_token(request.code)
        
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
    request: RefreshTokenRequest
) -> TokenResponse:
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
        new_token_data = await oauth_handler.refresh_token(
            token_data.get("refresh_token")
        )
        
        await token_manager.store_token(platform, request.user_id, new_token_data)
        
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
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found for this user"
            )
        
        content_dict = request.content.dict(exclude_none=True)
        
        result = await oauth_handler.create_post(
            token_data["access_token"],
            content_dict
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
    request: MediaUploadRequest = None,
) -> MediaUploadResponse:
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
        content = await file.read()
        
        result = await oauth_handler.upload_media(
            token_data["access_token"],
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

@router.post("/{platform}/profile", response_model=UserProfile)
async def get_profile(
    platform: str,
    request: ProfileRequest,
) -> UserProfile:
    try:
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
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