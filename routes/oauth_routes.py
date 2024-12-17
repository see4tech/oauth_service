from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from typing import Optional, Dict
from ..core import TokenManager
from ..platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth
from ..models.oauth_models import (
    OAuthInitRequest, OAuthInitResponse, OAuthCallbackRequest,
    TokenResponse, PostContent, PostResponse, MediaUploadResponse,
    UserProfile, ErrorResponse
)
from ..utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/oauth", tags=["oauth"])

async def get_oauth_handler(platform: str, client_id: str, client_secret: str, callback_url: str):
    """Get appropriate OAuth handler based on platform."""
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
    
    return handlers[platform](client_id, client_secret, callback_url)

@router.post("/{platform}/init", response_model=OAuthInitResponse)
async def initialize_oauth(
    platform: str,
    request: OAuthInitRequest
) -> OAuthInitResponse:
    """Initialize OAuth flow and get authorization URL."""
    try:
        oauth_handler = await get_oauth_handler(platform, client_id, client_secret, request.redirect_uri)
        state = oauth_handler.generate_state(request.user_id)
        
        auth_urls = await oauth_handler.get_authorization_url(
            state=state,
            extra_scopes=request.scopes
        )
        
        # Handle platforms with multiple authorization URLs (e.g., Twitter)
        if isinstance(auth_urls, dict):
            return OAuthInitResponse(
                authorization_url=auth_urls['oauth2_url'],
                state=state,
                platform=platform,
                additional_params={"oauth1_url": auth_urls.get('oauth1_url')}
            )
        
        return OAuthInitResponse(
            authorization_url=auth_urls,
            state=state,
            platform=platform
        )
        
    except Exception as e:
        logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/callback", response_model=TokenResponse)
async def oauth_callback(
    platform: str,
    request: OAuthCallbackRequest
) -> TokenResponse:
    """Handle OAuth callback and token exchange."""
    try:
        oauth_handler = await get_oauth_handler(platform, client_id, client_secret, request.redirect_uri)
        user_id = oauth_handler.verify_state(request.state)
        
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid state parameter"
            )
        
        token_manager = TokenManager()
        token_data = await oauth_handler.get_access_token(request.code)
        await token_manager.store_token(platform, user_id, token_data)
        
        return TokenResponse(**token_data)
        
    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/refresh", response_model=TokenResponse)
async def refresh_token(
    platform: str,
    user_id: str,
    refresh_token: str
) -> TokenResponse:
    """Refresh OAuth access token."""
    try:
        oauth_handler = await get_oauth_handler(platform, client_id, client_secret, "")
        token_manager = TokenManager()
        
        token_data = await oauth_handler.refresh_token(refresh_token)
        await token_manager.store_token(platform, user_id, token_data)
        
        return TokenResponse(**token_data)
        
    except Exception as e:
        logger.error(f"Error refreshing token for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/post", response_model=PostResponse)
async def create_post(
    platform: str,
    content: PostContent,
    user_id: str,
    authorization: str = Header(...)
) -> PostResponse:
    """Create a post on the specified platform."""
    try:
        oauth_handler = await get_oauth_handler(platform, client_id, client_secret, "")
        token_manager = TokenManager()
        
        tokens = await token_manager.get_valid_token(platform, user_id)
        if not tokens:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        result = await oauth_handler.create_post(tokens, content.dict())
        return PostResponse(
            post_id=result["post_id"],
            platform=platform,
            platform_specific_data=result.get("additional_data")
        )
        
    except Exception as e:
        logger.error(f"Error creating post on {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/media/upload", response_model=MediaUploadResponse)
async def upload_media(
    platform: str,
    user_id: str,
    file: UploadFile = File(...),
    authorization: str = Header(...)
) -> MediaUploadResponse:
    """Upload media to the specified platform."""
    try:
        oauth_handler = await get_oauth_handler(platform, client_id, client_secret, "")
        token_manager = TokenManager()
        
        tokens = await token_manager.get_valid_token(platform, user_id)
        if not tokens:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        content = await file.read()
        result = await oauth_handler.upload_media(tokens, content, file.filename)
        
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
    """Get user profile from the specified platform."""
    try:
        oauth_handler = await get_oauth_handler(platform, client_id, client_secret, "")
        token_manager = TokenManager()
        
        tokens = await token_manager.get_valid_token(platform, user_id)
        if not tokens:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )
        
        profile_data = await oauth_handler.get_user_profile(tokens)
        return UserProfile(
            id=profile_data["id"],
            platform=platform,
            raw_data=profile_data
        )
        
    except Exception as e:
        logger.error(f"Error fetching profile from {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
