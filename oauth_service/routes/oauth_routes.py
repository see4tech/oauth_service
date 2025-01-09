from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request, Query, Body
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from ..core import TokenManager
from ..core.db import SqliteDB
from ..core.oauth_base import OAuthBase
from ..platforms.twitter import TwitterOAuth
from ..platforms.linkedin import LinkedInOAuth
from ..platforms.facebook import FacebookOAuth
from ..platforms.instagram import InstagramOAuth
from ..models.oauth_models import (
    OAuthInitRequest, OAuthInitResponse, OAuthCallbackRequest,
    TokenResponse, PostContent, PostResponse, MediaUploadResponse, UserProfile
)
from ..utils.logger import get_logger
from ..config import get_settings
from fastapi.responses import RedirectResponse, JSONResponse
from .oauth_utils import get_oauth_handler, store_code_verifier, get_code_verifier
from .oauth_callbacks import init_twitter_oauth
from ..utils.crypto import generate_oauth_state
import json
from urllib.parse import urlparse, urljoin
from ..utils.encryption import encrypt_api_key

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

async def get_oauth_handler(platform: str, callback_url: Optional[str] = None) -> OAuthBase:
    """Get OAuth handler for specified platform."""
    try:
        settings = get_settings()
        
        if platform == "twitter":
            return TwitterOAuth(
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                consumer_key=settings.TWITTER_CONSUMER_KEY,
                consumer_secret=settings.TWITTER_CONSUMER_SECRET,
                callback_url=callback_url or settings.TWITTER_CALLBACK_URL
            )
        elif platform == "linkedin":
            return LinkedInOAuth(
                client_id=settings.LINKEDIN_CLIENT_ID,
                client_secret=settings.LINKEDIN_CLIENT_SECRET,
                callback_url=callback_url or settings.LINKEDIN_CALLBACK_URL
            )
        elif platform == "facebook":
            return FacebookOAuth(
                client_id=settings.FACEBOOK_CLIENT_ID,
                client_secret=settings.FACEBOOK_CLIENT_SECRET,
                callback_url=callback_url or settings.FACEBOOK_CALLBACK_URL
            )
        else:
            raise ValueError(f"Unsupported platform: {platform}")
            
    except Exception as e:
        logger.error(f"Error getting OAuth handler for {platform}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize {platform} OAuth handler: {str(e)}"
        )

@router.post("/{platform}/init", response_model=OAuthInitResponse)
async def initialize_oauth(
    platform: str, 
    request: OAuthInitRequest
) -> OAuthInitResponse:
    try:
        # For Twitter, use the settings callback URL as base
        if platform == "twitter":
            # Special handling for Twitter
            auth_data = await init_twitter_oauth(
                user_id=request.user_id,
                frontend_callback_url=request.frontend_callback_url,
                use_oauth1=request.use_oauth1
            )
            return OAuthInitResponse(
                **auth_data,
                platform=platform
            )
            
        # For other platforms, use the frontend callback URL as base
        parsed_url = urlparse(request.frontend_callback_url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        # Create version-specific callback URLs
        if platform == "linkedin":
            callback_url = urljoin(base_url, f"/oauth/{platform}/callback")  # No version suffix for LinkedIn
        else:
            callback_url = urljoin(base_url, f"/oauth/{platform}/callback/{'1' if request.use_oauth1 else '2'}")
        
        # Initialize OAuth handler with correct callback URL
        oauth_handler = await get_oauth_handler(platform, callback_url)
        logger.debug(f"Initialized OAuth handler for {platform} with callback URL: {callback_url}")
        
        # Standard OAuth 2.0 flow for other platforms
        state = generate_oauth_state(
            user_id=request.user_id,
            frontend_callback_url=request.frontend_callback_url,
            platform=platform
        )
        
        authorization_url = await oauth_handler.get_authorization_url(
            state=state,
            scopes=request.scopes
        )
        
        return OAuthInitResponse(
            authorization_url=authorization_url,
            state=state,
            platform=platform
        )
        
    except Exception as e:
        logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize {platform} OAuth: {str(e)}"
        )

async def store_code_verifier(state: str, code_verifier: str):
    """Store code verifier in Redis or another temporary storage."""
    # TODO: Implement storage mechanism
    # For now, we'll store it in memory (not suitable for production)
    if not hasattr(store_code_verifier, 'verifiers'):
        store_code_verifier.verifiers = {}
    store_code_verifier.verifiers[state] = code_verifier

async def get_code_verifier(state: str) -> Optional[str]:
    """Retrieve code verifier from storage."""
    if not hasattr(store_code_verifier, 'verifiers'):
        return None
    return store_code_verifier.verifiers.get(state)

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
        
        # Get user_id from state data
        user_id = state_data.get('user_id')
        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="No user_id in state data"
            )

        token_data = None
        
        # For Twitter, handle OAuth 1.0a and 2.0 separately
        if platform == "twitter":
            if request.oauth1_verifier:
                # OAuth 1.0a flow
                token_data = await oauth_handler.get_access_token(
                    oauth1_verifier=request.oauth1_verifier
                )
            else:
                # OAuth 2.0 flow
                code_verifier = await get_code_verifier(request.state)
                token_data = await oauth_handler.get_access_token(
                    oauth2_code=request.code,
                    code_verifier=code_verifier
                )
        else:
            # Standard OAuth 2.0 flow for other platforms
            token_data = await oauth_handler.get_access_token(request.code)
        
        if not token_data:
            raise HTTPException(
                status_code=400,
                detail="Failed to get access token"
            )

        # Store token data
        token_manager = TokenManager()
        await token_manager.store_token(
            platform=platform,
            user_id=user_id,
            token_data=token_data
        )
        
        # Store the API key as-is if it's in the token data
        if 'api_key' in token_data:
            logger.debug(f"Storing API key from token data - User: {user_id}, Platform: {platform}, Key: {token_data['api_key']}")
            db = SqliteDB()
            db.store_user_api_key(user_id, platform, token_data['api_key'])
        else:
            logger.debug(f"No API key found in token data for User: {user_id}, Platform: {platform}")
            logger.debug(f"Token data keys: {token_data.keys()}")

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

async def validate_api_keys(user_id: str, platform: str, x_api_key: str) -> bool:
    """Validate both global and user-specific API keys."""
    # Log non-sensitive information
    logger.debug("=== API Key Validation ===")
    logger.debug(f"Platform: {platform}")
    logger.debug(f"User ID: {user_id}")
    
    try:
        # Get user's stored API key
        db = SqliteDB()
        stored_api_key = db.get_user_api_key(user_id, platform)
        
        # Now do the validation
        if x_api_key != settings.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        if not stored_api_key:
            raise HTTPException(status_code=401, detail="No API key found for user")
            
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during API key validation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error during validation")

@router.post("/{platform}/post", response_model=PostResponse)
async def create_post(
    platform: str,
    request: SimplePostRequest,
    x_api_key: str = Header(..., alias="x-api-key")
) -> PostResponse:
    # Log non-sensitive information
    logger.debug("=== Processing Post Request ===")
    logger.debug(f"Platform: {platform}")
    logger.debug(f"User ID: {request.user_id}")
    
    # Get stored API key
    db = SqliteDB()
    stored_api_key = db.get_user_api_key(request.user_id, platform)
    
    try:
        # Validate against user's stored API key
        if x_api_key != stored_api_key:
            logger.debug("API key validation failed")
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        if not stored_api_key:
            logger.debug("No stored API key found")
            raise HTTPException(status_code=401, detail="No API key found for user")
        
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        # Get token data
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found for this user"
            )
        
        # Log token structure (without sensitive data)
        logger.debug(f"Token data structure: {list(token_data.keys() if isinstance(token_data, dict) else [])}")
        
        content_dict = request.content.dict(exclude_none=True)
        
        # For Twitter, ensure we have both OAuth 1.0a and 2.0 tokens if needed
        if platform == "twitter":
            if not isinstance(token_data, dict):
                raise HTTPException(
                    status_code=500,
                    detail="Invalid token data structure"
                )
            
            if content_dict.get("image_url") and 'oauth1' not in token_data:
                raise HTTPException(
                    status_code=400,
                    detail="OAuth 1.0a tokens required for media upload"
                )
            
            # Ensure OAuth 1.0a tokens are properly structured
            if 'oauth1' in token_data:
                oauth1_data = token_data['oauth1']
                if not isinstance(oauth1_data, dict):
                    raise HTTPException(
                        status_code=500,
                        detail="Invalid OAuth 1.0a token structure"
                    )
                if not oauth1_data.get('access_token') or not oauth1_data.get('access_token_secret'):
                    raise HTTPException(
                        status_code=401,
                        detail="Missing OAuth 1.0a tokens"
                    )
        
        result = await oauth_handler.create_post(
            token_data,
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
    user_id: str = Query(..., description="User ID"),
    api_key: str = Query(..., description="User's API key"),
    x_api_key: str = Header(..., alias="x-api-key")
) -> MediaUploadResponse:
    try:
        # Validate API keys
        await validate_api_keys(user_id, platform, x_api_key)
        
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        token_data = await token_manager.get_valid_token(platform, user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found"
            )
        
        content = await file.read()
        
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

@router.post("/{platform}/store_token")
async def store_oauth_token(platform: str, token_data: dict):
    try:
        user_id = token_data.get("user_id")
        api_key = token_data.get("api_key")
        
        if not user_id or not api_key:
            raise HTTPException(status_code=400, detail="Missing user_id or api_key")
            
        # Store the API key as-is
        db = SqliteDB()
        db.store_user_api_key(user_id, platform, api_key)
        
        return {"status": "success", "message": "API key stored successfully"}
    except Exception as e:
        logger.error(f"Error storing OAuth token: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/twitter/post")
async def post_twitter_content(
    request: Request,
    user_id: str = Body(...),
    content: Dict = Body(...),
    x_api_key: str = Header(..., alias="x-api-key")
):
    """Post content to Twitter."""
    try:
        logger.debug("=== Processing Post Request ===")
        logger.debug(f"Platform: twitter")
        logger.debug(f"User ID: {user_id}")
        
        # Get stored API key for validation - just check oauth1 since they're the same
        db = SqliteDB()
        stored_key = db.get_user_api_key(user_id, "twitter-oauth1")
        
        if not stored_key or stored_key != x_api_key:
            logger.debug("API key validation failed")
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Initialize Twitter OAuth handler
        oauth_handler = await get_oauth_handler("twitter")
        
        # Check if we have an image to upload
        if "image_url" in content:
            # Use combined method for media upload and tweet
            response = await oauth_handler.post_tweet_with_media(
                user_id=user_id,
                text=content["text"],
                image_url=content["image_url"]
            )
        else:
            # Simple text-only tweet using OAuth 2.0
            token_manager = TokenManager()
            tokens = await token_manager.get_token("twitter", user_id)
            oauth2_token = tokens.get('oauth2', {}).get('access_token')
            
            response = await oauth_handler.post_tweet(
                access_token=oauth2_token,
                text=content["text"],
                oauth_version="oauth2"
            )
        
        return {"success": True, "response": response}
        
    except Exception as e:
        logger.error(f"Error creating post on twitter: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))