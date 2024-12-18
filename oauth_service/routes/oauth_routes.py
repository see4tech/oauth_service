from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile
from typing import Optional, Dict
from ..core import TokenManager
from ..platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth
from ..models.oauth_models import (
    OAuthInitRequest,
    OAuthInitResponse,
    OAuthCallbackRequest,
    TokenResponse,
    PostContent,
    PostResponse,
    MediaUploadResponse,
    UserProfile
)
from ..utils.logger import get_logger
from ..config import get_settings
import json

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

async def get_oauth_handler(platform: str):
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
    
    try:
        credentials = settings.get_platform_credentials(platform)
        return handlers[platform](**credentials)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/init", response_model=OAuthInitResponse)
async def initialize_oauth(
    platform: str,
    request: OAuthInitRequest
) -> OAuthInitResponse:
    """Initialize OAuth flow and get authorization URL."""
    try:
        oauth_handler = await get_oauth_handler(platform)
        state = oauth_handler.generate_state(request.user_id)
        
        # Changed here: using 'scopes' instead of 'extra_scopes'
        auth_url = await oauth_handler.get_authorization_url(
            state=state,
            scopes=request.scopes
        )
        
        return OAuthInitResponse(
            authorization_url=auth_url,
            state=state,
            platform=platform
        )
        
    except Exception as e:
        logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ... rest of the routes ...
