from fastapi import APIRouter, Depends, HTTPException, Header, File, UploadFile, Request, Query
from typing import Optional, Dict, List
from pydantic import BaseModel, Field
from ..core import TokenManager
from ..core.db import SqliteDB
from ..platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth
from ..models.oauth_models import (
    OAuthInitRequest, OAuthInitResponse, OAuthCallbackRequest,
    TokenResponse, PostContent, PostResponse, MediaUploadResponse, UserProfile
)
from ..utils.logger import get_logger
from ..config import get_settings
from fastapi.responses import RedirectResponse, JSONResponse
import json

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()

class APIKeyLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith("/post"):
            logger.debug("=== Raw Request Debug Info ===")
            logger.debug(f"Platform: {request.path_params.get('platform')}")
            logger.debug(f"Headers: {dict(request.headers)}")
            logger.debug(f"x-api-key header: {request.headers.get('x-api-key')}")
            logger.debug(f"Settings API_KEY: {settings.API_KEY}")
            
            # Log request body
            try:
                body = await request.json()
                logger.debug(f"Request body: {body}")
                
                # Get stored API key
                if body.get('user_id'):
                    db = SqliteDB()
                    stored_api_key = db.get_user_api_key(body['user_id'], request.path_params.get('platform'))
                    logger.debug(f"Stored API key for user: {stored_api_key}")
            except:
                logger.debug("Could not read request body")
        
        response = await call_next(request)
        return response

# Add middleware to router
router.middleware("http")(APIKeyLoggingMiddleware())

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
        
        # For Twitter, pass both OAuth 1.0a and 2.0 credentials
        if platform == "twitter":
            oauth_credentials = {
                "client_id": credentials["client_id"],  # OAuth 2.0 client ID
                "client_secret": credentials["client_secret"],  # OAuth 2.0 client secret
                "consumer_key": credentials["consumer_key"],  # OAuth 1.0a key
                "consumer_secret": credentials["consumer_secret"],  # OAuth 1.0a secret
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
            # Store code verifier in state for later use
            if isinstance(auth_urls, dict) and 'code_verifier' in auth_urls:
                await store_code_verifier(state, auth_urls['code_verifier'])
                
            return OAuthInitResponse(
                authorization_url=auth_urls['oauth2_url'],
                state=auth_urls['state'],
                platform=platform,
                additional_params={
                    'oauth1_url': auth_urls.get('oauth1_url'),
                    'oauth1_error': auth_urls.get('oauth1_error')
                }
            )
        
        # For other platforms that return a string URL directly
        if isinstance(auth_urls, str):
            return OAuthInitResponse(
                authorization_url=auth_urls,
                state=state,
                platform=platform
            )
            
        # For other platforms that return a dictionary
        return OAuthInitResponse(
            authorization_url=auth_urls['oauth2_url'] if 'oauth2_url' in auth_urls else auth_urls['authorization_url'],
            state=auth_urls.get('state', state),
            platform=platform
        )
        
    except Exception as e:
        logger.error(f"Error initializing OAuth for {platform}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
                # Get code verifier from storage
                code_verifier = await get_code_verifier(request.state)
                if not code_verifier:
                    raise HTTPException(
                        status_code=400,
                        detail="Code verifier not found"
                    )
                
                token_data = await oauth_handler.get_access_token(
                    oauth2_code=request.code,
                    code_verifier=code_verifier
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

async def validate_api_keys(user_id: str, platform: str, x_api_key: str) -> bool:
    """Validate both global and user-specific API keys."""
    # Log keys first, before any validation
    logger.debug("=== API Key Debug Info ===")
    logger.debug(f"Platform: {platform}")
    logger.debug(f"User ID: {user_id}")
    logger.debug(f"x-api-key from header: {x_api_key}")
    logger.debug(f"Expected API key from settings: {settings.API_KEY}")
    
    try:
        # Get user's stored API key first for logging
        db = SqliteDB()
        stored_api_key = db.get_user_api_key(user_id, platform)
        logger.debug(f"Stored API key for user: {stored_api_key}")
        
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
    # Log API key information immediately
    logger.debug("=== API Key Debug Info ===")
    logger.debug(f"Platform: {platform}")
    logger.debug(f"User ID: {request.user_id}")
    logger.debug(f"x-api-key header: {x_api_key}")
    logger.debug(f"Settings API_KEY: {settings.API_KEY}")
    
    # Get and log stored API key
    db = SqliteDB()
    stored_api_key = db.get_user_api_key(request.user_id, platform)
    logger.debug(f"Stored API key for user: {stored_api_key}")
    
    try:
        # Continue with validation
        if x_api_key != settings.API_KEY:
            logger.debug("API key validation failed")
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        if not stored_api_key:
            logger.debug("No stored API key found")
            raise HTTPException(status_code=401, detail="No API key found for user")
        
        oauth_handler = await get_oauth_handler(platform)
        token_manager = TokenManager()
        
        token_data = await token_manager.get_valid_token(platform, request.user_id)
        if not token_data:
            raise HTTPException(
                status_code=401,
                detail="No valid token found for this user"
            )
        
        content_dict = request.content.dict(exclude_none=True)
        
        # Special handling for Twitter with media
        if platform == "twitter" and content_dict.get("image_url"):
            # First upload media using v1.1 API
            media_id = await oauth_handler.upload_media_v1(
                token_data,
                content_dict["image_url"]
            )
            # Then create tweet with media_id using v2 API
            content_dict["media_ids"] = [media_id]
            del content_dict["image_url"]  # Remove image_url as we now have media_id
        
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