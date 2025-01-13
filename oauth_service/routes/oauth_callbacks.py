from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, Dict
from ..core import TokenManager
from ..utils.logger import get_logger
from .oauth_utils import get_oauth_handler, get_code_verifier, store_code_verifier
from ..core.db import SqliteDB
from ..config import get_settings
from ..api.api_key_storage import APIKeyStorage
from ..utils.crypto import generate_api_key, generate_oauth_state
from ..platforms import TwitterOAuth
import json
import os
import base64
import aiohttp
from datetime import datetime
import logging
import time

logger = get_logger(__name__)
callback_router = APIRouter()
settings = get_settings()

# Cache to store recently processed auth codes with timestamps
_processed_codes: Dict[str, float] = {}
_CACHE_EXPIRY = 60  # Clear codes from cache after 60 seconds

async def _is_code_processed(code: str) -> bool:
    """Check if an authorization code was already processed."""
    current_time = time.time()
    # Clean expired entries
    expired = [k for k, v in _processed_codes.items() if current_time - v > _CACHE_EXPIRY]
    for k in expired:
        del _processed_codes[k]
    return code in _processed_codes

async def _mark_code_processed(code: str) -> None:
    """Mark an authorization code as processed."""
    _processed_codes[code] = time.time()

async def get_stored_user_id(oauth_token: str) -> Optional[str]:
    """Get stored user_id for OAuth 1.0a token."""
    try:
        # We're reusing the code_verifier storage for OAuth 1.0a tokens
        user_id = await get_code_verifier(oauth_token)
        logger.debug(f"Retrieved user_id {user_id} for OAuth token {oauth_token[:10]}...")
        return user_id
    except Exception as e:
        logger.error(f"Error retrieving user_id for OAuth token: {str(e)}")
        return None

async def init_twitter_oauth(user_id: str, frontend_callback_url: str, use_oauth1: bool = False) -> dict:
    """Initialize Twitter OAuth flow."""
    try:
        settings = get_settings()
        
        # Get base callback URL from settings
        base_callback_url = settings.TWITTER_CALLBACK_URL.rstrip('/')  # Remove any trailing slash
        
        # Append version to callback URL
        callback_url = f"{base_callback_url}/{'1' if use_oauth1 else '2'}"
        
        logger.debug(f"Twitter OAuth initialization:")
        logger.debug(f"Base callback URL from settings: {base_callback_url}")
        logger.debug(f"OAuth version: {'1.0a' if use_oauth1 else '2.0'}")
        logger.debug(f"Final callback URL: {callback_url}")
        
        oauth = TwitterOAuth(
            client_id=settings.TWITTER_CLIENT_ID,
            client_secret=settings.TWITTER_CLIENT_SECRET,
            consumer_key=settings.TWITTER_CONSUMER_KEY,
            consumer_secret=settings.TWITTER_CONSUMER_SECRET,
            callback_url=callback_url
        )
        
        # Generate and encrypt state - we'll use this for both OAuth 1.0a and 2.0
        state = generate_oauth_state(
            user_id=user_id,
            frontend_callback_url=frontend_callback_url,
            platform="twitter"
        )
        
        # Get authorization URL and await it since it's async
        auth_data = await oauth.get_authorization_url()
        
        # Get the correct URL based on OAuth version
        auth_url = auth_data['oauth1_url'] if use_oauth1 else auth_data['oauth2_url']
        
        # Store code verifier if this is OAuth 2.0
        if not use_oauth1 and 'code_verifier' in auth_data:
            logger.debug(f"Storing code verifier for state: {state}")
            await store_code_verifier(state, auth_data['code_verifier'])
        
        # For OAuth 1.0a, store the request token with user_id
        if use_oauth1:
            # For OAuth 1.0a, we need to extract the oauth_token from the URL
            oauth_token = None
            if 'oauth1_url' in auth_data:
                from urllib.parse import urlparse, parse_qs
                parsed = urlparse(auth_data['oauth1_url'])
                query_params = parse_qs(parsed.query)
                oauth_token = query_params.get('oauth_token', [None])[0]
            
            if oauth_token:
                logger.debug(f"Storing user_id {user_id} with request token {oauth_token}")
                await store_code_verifier(oauth_token, user_id)  # Reuse code_verifier storage for user_id
            else:
                logger.error("No oauth_token found in auth_data")
                raise ValueError("Failed to get OAuth 1.0a request token")
        
        # For OAuth 1.0a, don't append state as it uses oauth_token
        if not use_oauth1:
            # Manually append state to URL only for OAuth 2.0
            separator = '&' if '?' in auth_url else '?'
            auth_url = f"{auth_url}{separator}state={state}"
        
        logger.debug(f"Generated authorization URL: {auth_url}")
        
        return {
            "authorization_url": auth_url,
            "state": state,  # Always return state for both OAuth 1.0a and 2.0
            "code_verifier": auth_data.get('code_verifier')  # Include code_verifier for OAuth 2.0
        }
    except Exception as e:
        logger.error(f"Error initializing OAuth for twitter: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize Twitter OAuth: {str(e)}"
        )

@callback_router.get("/linkedin/callback", include_in_schema=True)
async def linkedin_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
) -> HTMLResponse:
    """Handle LinkedIn OAuth callback"""
    logger.info("=== LinkedIn OAuth Callback Start ===")
    
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    
    logger.info(f"Code present: {bool(code)}")
    logger.info(f"State present: {bool(state)}")
    
    if not code or not state:
        error_msg = "Missing code or state parameter"
        logger.error(f"Error in LinkedIn callback: {error_msg}")
        return create_html_response(success=False, error=error_msg)
    
    # Check if this code was already processed
    if await _is_code_processed(code):
        logger.info(f"Skipping duplicate callback for code: {code[:10]}...")
        return create_html_response(
            success=True,
            error=None,
            platform="linkedin",
            auto_close=True
        )
    
    try:
        # Initialize OAuth handler
        oauth_handler = await get_oauth_handler("linkedin")
        
        # Verify state
        logger.info(f"Attempting to verify state: {state}")
        state_data = oauth_handler.verify_state(state)
        if not state_data:
            return create_html_response(
                error="Invalid state",
                platform="linkedin",
                auto_close=True
            )
        
        logger.info(f"State verification successful. State data: {state_data}")
        user_id = state_data['user_id']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        try:
            # Exchange code for tokens
            tokens = await oauth_handler.get_access_token(code)
            logger.debug(f"Received tokens from LinkedIn: {tokens}")
            
            # Store OAuth tokens first
            token_manager = TokenManager()
            await token_manager.store_token(
                platform="linkedin",
                user_id=user_id,
                token_data=tokens
            )
            logger.info(f"Stored OAuth tokens for user {user_id}")
            
            # Generate and store API key
            api_key = generate_api_key()
            logger.info("=== API Key Generation ===")
            logger.info(f"Generated API key: {api_key}")
            
            # Prepare payload for external storage
            external_storage_payload = {
                "user_id": user_id,
                "platform": "linkedin",
                "api_key": api_key
            }
            logger.info("=== External Storage Request ===")
            logger.info(f"Full payload being sent to external storage: {external_storage_payload}")
            logger.info(f"Headers for external storage: x-api-key: {api_key}")
            
            # Store API key in external service first
            api_key_storage = APIKeyStorage()
            stored = await api_key_storage.store_api_key(
                user_id=user_id,
                platform="linkedin",
                api_key=api_key
            )
            
            if not stored:
                raise ValueError("Failed to store API key in external service")
            logger.info("Successfully stored API key in external service")
            
            # Store the SAME api_key locally
            try:
                logger.info("=== Local Database Storage ===")
                logger.info(f"Attempting to store in SQLite - User ID: {user_id}, Platform: linkedin, API Key: {api_key}")
                
                db = SqliteDB()
                db.store_user_api_key(user_id, platform="linkedin", api_key=api_key)
                logger.info("Successfully stored API key in local database")
                
                # Verify the stored key
                stored_key = db.get_user_api_key(user_id, "linkedin")
                logger.info("=== Local Storage Verification ===")
                logger.info("API key storage verification completed")
                
                if stored_key != api_key:
                    logger.error("Stored key verification failed - mismatch between stored and original")
                    logger.error(f"Original length: {len(api_key)}, Stored length: {len(stored_key) if stored_key else 0}")
            except Exception as e:
                logger.error(f"Failed to store API key in local database: {str(e)}")
                raise
            
            logger.info("=== LinkedIn OAuth Flow Complete ===")
            logger.info(f"Successfully stored API key for user {user_id} in both external and local storage")
            success = True
            
            # Return success response with API key for frontend
            message_type = "LINKEDIN_AUTH_CALLBACK"
            html_content = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>LinkedIn OAuth Callback</title>
                </head>
                <body>
                    <h2>Authentication Successful</h2>
                    <p>This window will close automatically.</p>
                    <script>
                        const message = {{
                            type: '{message_type}',
                            success: true,
                            api_key: '{api_key}',
                            platform: 'linkedin'
                        }};
                        
                        if (window.opener) {{
                            window.opener.postMessage(message, '*');
                            console.log('Message sent:', message);
                        }}
                        
                        // Close window immediately
                        window.close();
                        
                        // Fallback if window.close() doesn't work
                        setTimeout(() => {{
                            window.location.href = 'about:blank';
                            window.close();
                        }}, 100);
                    </script>
                </body>
                </html>
            """
            
            # If we get here, mark the code as processed
            await _mark_code_processed(code)
            
            return HTMLResponse(content=html_content)
            
        except Exception as e:
            logger.error(f"Error in LinkedIn callback: {str(e)}")
            return create_html_response(
                error=str(e),
                platform="linkedin",
                auto_close=True
            )
        
    except Exception as e:
        logger.error(f"LinkedIn callback error: {str(e)}")
        return create_html_response(
            error=str(e),
            platform="linkedin",
            auto_close=True
        )

@callback_router.get("/{platform}/callback", include_in_schema=True)
async def oauth_callback(
    request: Request,
    platform: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """Handle OAuth callbacks for platforms other than LinkedIn."""
    try:
        logger.info(f"Received {platform.title()} callback")
        logger.info(f"Code present: {bool(code)}")
        logger.info(f"State present: {bool(state)}")
        
        # Initialize OAuth handler
        oauth_handler = await get_oauth_handler(platform)
        
        # Verify state and extract user_id
        logger.info(f"Attempting to verify state: {state}")
        state_data = oauth_handler.verify_state(state)
        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        logger.info(f"State verification successful. State data: {state_data}")
        
        user_id = state_data.get('user_id')
        logger.info(f"Processing callback for user_id: {user_id}")
        
        # Exchange code for token
        token_data = await oauth_handler.get_access_token(code)
        
        # Store API key if present
        if 'api_key' in token_data:
            logger.debug(f"API key present in token data: {token_data['api_key'][:10]}...")
            try:
                db = SqliteDB()
                db.store_user_api_key(user_id, platform, token_data['api_key'])
                logger.info(f"Successfully stored API key for user {user_id}")
            except Exception as e:
                logger.error(f"Error storing API key: {str(e)}")
        
        return create_html_response(
            platform=platform,
            success=True,
            auto_close=True
        )
    except Exception as e:
        logger.error(f"Error in OAuth callback: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def create_html_response(
    error: Optional[str] = None,
    platform: Optional[str] = None,
    version: Optional[str] = None,
    auto_close: bool = False,
    success: bool = False
) -> HTMLResponse:
    """Create HTML response for OAuth callback."""
    
    message_type = f"{platform.upper()}_AUTH_CALLBACK" if platform else "OAUTH_CALLBACK"
    
    html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Callback</title>
        </head>
        <body>
            <h2>{error and 'Authentication Failed' or 'Authentication Successful'}</h2>
            <p>{error or 'This window will close automatically.'}</p>
            <script>
                const message = {{
                    type: '{message_type}',
                    success: {json.dumps(success and not error)},
                    error: {json.dumps(error)},
                    platform: {json.dumps(platform)},
                    version: {json.dumps(version)}
                }};
                
                if (window.opener) {{
                    window.opener.postMessage(message, '*');
                    console.log('Message sent:', message);
                }}
                
                // Close window immediately
                window.close();
                
                // Fallback if window.close() doesn't work
                setTimeout(() => {{
                    window.location.href = 'about:blank';
                    window.close();
                }}, 100);
            </script>
        </body>
        </html>
    """
    
    return HTMLResponse(content=html_content)

@callback_router.get("/twitter/callback/1")
async def twitter_oauth1_callback(
    request: Request,
    oauth_token: Optional[str] = None,
    oauth_verifier: Optional[str] = None
) -> HTMLResponse:
    """Handle Twitter OAuth 1.0a callback."""
    try:
        logger.info("=== Twitter OAuth 1.0a Callback Start ===")
        logger.info(f"OAuth token present: {bool(oauth_token)}")
        logger.info(f"OAuth verifier present: {bool(oauth_verifier)}")
        
        if not oauth_token or not oauth_verifier:
            return create_html_response(
                error="Missing OAuth parameters",
                platform="twitter",
                version="1",
                auto_close=True
            )
        
        # Get user_id from stored request token
        user_id = await get_stored_user_id(oauth_token)
        if not user_id:
            return create_html_response(
                error="Invalid OAuth token",
                platform="twitter",
                version="1",
                auto_close=True
            )
            
        logger.info(f"Processing callback for user_id: {user_id}")
        
        # Initialize OAuth handler
        oauth_handler = await get_oauth_handler("twitter")
        
        # Exchange verifier for access token
        token_data = await oauth_handler.get_oauth1_access_token(oauth_token, oauth_verifier)
        
        # Store tokens
        token_manager = TokenManager()
        await token_manager.store_token(
            platform="twitter",
            user_id=user_id,
            token_data={'oauth1': token_data}
        )
        
        # Check for existing Twitter API key first
        db = SqliteDB()
        existing_api_key = db.get_user_api_key(user_id, "twitter-oauth1")

        if existing_api_key:
            # Reuse the existing API key for OAuth 2.0
            api_key = existing_api_key
            logger.info("=== Reusing Existing Twitter API Key ===")
            logger.info("Using existing API key from OAuth 1.0a")
        else:
            # Generate new API key if none exists
            api_key = generate_api_key()
            logger.info("=== API Key Generation ===")
            logger.info("Generated new API key")
        
        # Store with oauth1 suffix
        platform_with_version = "twitter-oauth1"
        
        # Prepare payload for external storage
        external_storage_payload = {
            "user_id": user_id,
            "platform": platform_with_version,  # "twitter-oauth1"
            "api_key": api_key
        }
        
        # Store API key in external service
        api_key_storage = APIKeyStorage()
        stored = await api_key_storage.store_api_key(
            user_id=user_id,
            platform=platform_with_version,
            api_key=api_key
        )
        if not stored:
            raise ValueError("Failed to store API key in external service")
        logger.info(f"Successfully stored API key in external service for {platform_with_version}")
        
        # Store the SAME api_key locally
        try:
            logger.info("=== Local Database Storage ===")
            logger.info(f"Attempting to store in SQLite - User ID: {user_id}, Platform: {platform_with_version}, API Key: {api_key}")
            
            db = SqliteDB()
            db.store_user_api_key(user_id, platform=platform_with_version, api_key=api_key)
            logger.info(f"Successfully stored API key in local database for {platform_with_version}")
            
            # Verify the stored key
            stored_key = db.get_user_api_key(user_id, platform_with_version)
            logger.info("=== Local Storage Verification ===")
            logger.info("API key storage verification completed")
            
            if stored_key != api_key:
                logger.error("Stored key verification failed - mismatch between stored and original")
                logger.error(f"Original length: {len(api_key)}, Stored length: {len(stored_key) if stored_key else 0}")
        except Exception as e:
            logger.error(f"Failed to store API key in local database: {str(e)}")
            raise
        
        return create_html_response(
            platform="twitter",
            version="1",
            success=True,
            auto_close=True
        )
        
    except Exception as e:
        logger.error(f"Error in Twitter OAuth 1.0a callback: {str(e)}")
        return create_html_response(
            error=str(e),
            platform="twitter",
            version="1",
            auto_close=True
        )

@callback_router.get("/twitter/callback/2")
async def twitter_oauth2_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None
) -> HTMLResponse:
    """Handle Twitter OAuth 2.0 callback."""
    try:
        logger.info("=== Twitter OAuth 2.0 Callback Start ===")
        logger.info(f"Code present: {bool(code)}")
        logger.info(f"State present: {bool(state)}")
        
        if not code or not state:
            return create_html_response(
                error="Missing OAuth parameters",
                platform="twitter",
                version="2",
                auto_close=True
            )
        
        # Initialize OAuth handler
        oauth_handler = await get_oauth_handler("twitter")
        
        # Verify state and extract user_id
        state_data = oauth_handler.verify_state(state)
        if not state_data:
            return create_html_response(
                error="Invalid state",
                platform="twitter",
                version="2",
                auto_close=True
            )
        
        user_id = state_data['user_id']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        # Get code verifier
        code_verifier = await get_code_verifier(state)
        if not code_verifier:
            return create_html_response(
                error="Invalid code verifier",
                platform="twitter",
                version="2",
                auto_close=True
            )
        
        # Exchange code for tokens
        token_data = await oauth_handler.get_access_token(oauth2_code=code, code_verifier=code_verifier)
        
        # Store tokens
        token_manager = TokenManager()
        await token_manager.store_token(
            platform="twitter",
            user_id=user_id,
            token_data={'oauth2': token_data}
        )
        
        # Check for existing Twitter API key first
        db = SqliteDB()
        existing_api_key = db.get_user_api_key(user_id, "twitter-oauth1")

        if existing_api_key:
            # Reuse the existing API key for OAuth 2.0
            api_key = existing_api_key
            logger.info("=== Reusing Existing Twitter API Key ===")
            logger.info("Using existing API key from OAuth 1.0a")
        else:
            # Generate new API key if none exists
            api_key = generate_api_key()
            logger.info("=== API Key Generation ===")
            logger.info("Generated new API key")
        
        # Store with oauth2 suffix
        platform_with_version = "twitter-oauth2"
        
        # Prepare payload for external storage
        external_storage_payload = {
            "user_id": user_id,
            "platform": platform_with_version,  # "twitter-oauth2"
            "api_key": api_key
        }
        
        # Store API key in external service
        api_key_storage = APIKeyStorage()
        stored = await api_key_storage.store_api_key(
            user_id=user_id,
            platform=platform_with_version,
            api_key=api_key
        )
        if not stored:
            raise ValueError("Failed to store API key in external service")
        logger.info(f"Successfully stored API key in external service for {platform_with_version}")
        
        # Store the SAME api_key locally
        try:
            logger.info("=== Local Database Storage ===")
            logger.info(f"Attempting to store in SQLite - User ID: {user_id}, Platform: {platform_with_version}, API Key: {api_key}")
            
            db = SqliteDB()
            db.store_user_api_key(user_id, platform=platform_with_version, api_key=api_key)
            logger.info(f"Successfully stored API key in local database for {platform_with_version}")
            
            # Verify the stored key
            stored_key = db.get_user_api_key(user_id, platform_with_version)
            logger.info("=== Local Storage Verification ===")
            logger.info("API key storage verification completed")
            
            if stored_key != api_key:
                logger.error("Stored key verification failed - mismatch between stored and original")
                logger.error(f"Original length: {len(api_key)}, Stored length: {len(stored_key) if stored_key else 0}")
        except Exception as e:
            logger.error(f"Failed to store API key in local database: {str(e)}")
            raise
        
        return create_html_response(
            platform="twitter",
            version="2",
            success=True,
            auto_close=True
        )
        
    except Exception as e:
        logger.error(f"Error in Twitter OAuth 2.0 callback: {str(e)}")
        return create_html_response(
            error=str(e),
            platform="twitter",
            version="2",
            auto_close=True
        )