from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request
from typing import Optional, Dict
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

async def get_oauth_handler(platform: str):
    handlers = {
        "twitter": TwitterOAuth,
        "linkedin": LinkedInOAuth,
        "instagram": InstagramOAuth,
        "facebook": FacebookOAuth
    }
    
    if platform not in handlers:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {platform}")
    
    try:
        credentials = settings.get_platform_credentials(platform)
        return handlers[platform](**credentials)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{platform}/init", response_model=OAuthInitResponse)
async def initialize_oauth(platform: str, request: OAuthInitRequest) -> OAuthInitResponse:
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
        
        return OAuthInitResponse(
            authorization_url=auth_url,
            state=state,
            platform=platform
        )
        
    except Exception as e:
        logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{platform}/callback")
async def oauth_callback(request: Request, platform: str) -> RedirectResponse:
    try:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state parameter")

        oauth_handler = await get_oauth_handler(platform)
        state_data = oauth_handler.verify_state(state)
        
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        user_id = state_data['user_id']
        frontend_callback_url = state_data['frontend_callback_url']
        
        token_manager = TokenManager()
        token_data = await oauth_handler.get_access_token(code)
        await token_manager.store_token(platform, user_id, token_data)
        
        return RedirectResponse(
            url=f"{frontend_callback_url}?platform={platform}&status=success&user_id={user_id}"
        )
        
    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        if 'frontend_callback_url' in locals():
            return RedirectResponse(
                url=f"{frontend_callback_url}?platform={platform}&status=error&message={str(e)}"
            )
        raise HTTPException(status_code=500, detail=str(e))

# Rest of the routes (refresh_token, create_post, etc.) remain the same...
