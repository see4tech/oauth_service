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
        
        # Get authorization URLs
        auth_urls = await oauth_handler.get_authorization_url(state=state)
        
        # For Twitter, handle the case where OAuth 1.0a might fail
        if platform == "twitter":
            return OAuthInitResponse(
                authorization_url=auth_urls['oauth2_url'],
                state=auth_urls['state'],
                platform=platform,
                additional_params={
                    'oauth1_url': auth_urls.get('oauth1_url'),
                    'oauth1_error': auth_urls.get('oauth1_error')
                }
            )
        
        # For other platforms
        return OAuthInitResponse(
            authorization_url=auth_urls['oauth2_url'] if isinstance(auth_urls, dict) else auth_urls,
            state=auth_urls.get('state', state),
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
        
        # For Twitter, handle OAuth 1.0a and 2.0 separately
        if platform == "twitter":
            # Check if this is an OAuth 1.0a callback
            if request.oauth1_verifier:
                token_data = await oauth_handler.get_access_token(
                    oauth1_verifier=request.oauth1_verifier
                )
                if not token_data or 'oauth1' not in token_data:
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to get OAuth 1.0a tokens"
                    )
                oauth1_data = token_data['oauth1']
                return TokenResponse(
                    access_token=oauth1_data["access_token"],
                    token_type="OAuth1",
                    expires_in=0,  # OAuth 1.0a tokens don't expire
                    access_token_secret=oauth1_data["access_token_secret"]
                )
            # Otherwise, treat as OAuth 2.0
            else:
                token_data = await oauth_handler.get_access_token(
                    oauth2_code=request.code
                )
                if not token_data or 'oauth2' not in token_data:
                    raise HTTPException(
                        status_code=400,
                        detail="Failed to get OAuth 2.0 tokens"
                    )
                oauth2_data = token_data['oauth2']
                return TokenResponse(
                    access_token=oauth2_data["access_token"],
                    token_type="Bearer",
                    expires_in=oauth2_data.get("expires_in", 3600),
                    refresh_token=oauth2_data.get("refresh_token"),
                    scope=oauth2_data.get("scope")
                )
        else:
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