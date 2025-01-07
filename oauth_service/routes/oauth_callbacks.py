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

logger = get_logger(__name__)
callback_router = APIRouter()
settings = get_settings()

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
        
        # Generate and encrypt state
        state = generate_oauth_state(
            user_id=user_id,
            frontend_callback_url=frontend_callback_url,
            platform="twitteroauth"
        )
        
        # Get authorization URL and await it since it's async
        auth_data = await oauth.get_authorization_url()
        
        # Get the correct URL based on OAuth version
        auth_url = auth_data['oauth1_url'] if use_oauth1 else auth_data['oauth2_url']
        
        # Store code verifier if this is OAuth 2.0
        if not use_oauth1 and 'code_verifier' in auth_data:
            logger.debug(f"Storing code verifier for state: {state}")
            await store_code_verifier(state, auth_data['code_verifier'])
        
        # Manually append state to URL
        separator = '&' if '?' in auth_url else '?'
        auth_url = f"{auth_url}{separator}state={state}"
        
        logger.debug(f"Generated authorization URL: {auth_url}")
        
        return {
            "authorization_url": auth_url,
            "state": state,
            "code_verifier": auth_data.get('code_verifier')  # Include code_verifier for OAuth 2.0
        }
    except Exception as e:
        logger.error(f"Error initializing OAuth for twitter: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize Twitter OAuth: {str(e)}"
        )

@callback_router.get("/{platform}/callback/{version}")
async def oauth_callback(
    request: Request,
    platform: str,
    version: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
) -> HTMLResponse:
    """Handle OAuth callback for platforms that use versioned callbacks (Twitter)"""
    if platform == "linkedin":
        # Redirect LinkedIn callbacks to the dedicated endpoint
        return RedirectResponse(url=f"/oauth/linkedin/callback?{request.query_params}")
    
    try:
        logger.info(f"Received callback for platform: {platform}, version: {version}")
        logger.info(f"Code present: {bool(code)}")
        logger.info(f"State present: {bool(state)}")
        logger.debug(f"Actual state value received: {state}")
        
        # Handle OAuth errors
        if error:
            logger.error(f"OAuth error: {error}")
            logger.error(f"Error description: {error_description}")
            return create_html_response(
                error=error_description or error,
                platform=platform,
                version=version,
                auto_close=True
            )

        success = False
        try:
            if platform == "twitter":
                # Twitter-specific handling with OAuth 1.0a and 2.0
                settings = get_settings()
                
                # Get base callback URL from settings and append version
                base_callback_url = settings.TWITTER_CALLBACK_URL.rstrip('/')
                callback_url = f"{base_callback_url}/{version}"
                
                logger.debug(f"Using callback URL for token exchange: {callback_url}")
                
                # Initialize OAuth handler with the same callback URL
                oauth = TwitterOAuth(
                    client_id=settings.TWITTER_CLIENT_ID,
                    client_secret=settings.TWITTER_CLIENT_SECRET,
                    consumer_key=settings.TWITTER_CONSUMER_KEY,
                    consumer_secret=settings.TWITTER_CONSUMER_SECRET,
                    callback_url=callback_url
                )
                
                # Get OAuth 1.0a parameters
                oauth_token = request.query_params.get('oauth_token')
                oauth_verifier = request.query_params.get('oauth_verifier')
                
                if version == "1":
                    # Twitter OAuth 1.0a flow
                    if not oauth_token or not oauth_verifier:
                        return create_html_response(
                            error="Missing OAuth 1.0a parameters",
                            platform=platform,
                            version=version,
                            auto_close=True
                        )
                    # Process OAuth 1.0a...
                    success = True
                else:
                    # Twitter OAuth 2.0 flow
                    if not code or not state:
                        return create_html_response(
                            error="Missing OAuth 2.0 parameters",
                            platform=platform,
                            version=version,
                            auto_close=True
                        )
                    
                    # Get code verifier for PKCE
                    code_verifier = await get_code_verifier(state)
                    if not code_verifier:
                        logger.error("Code verifier not found for state")
                        return create_html_response(
                            error="Code verifier not found",
                            platform=platform,
                            version=version,
                            auto_close=True
                        )
                        
                    logger.debug(f"Found code verifier for state: {bool(code_verifier)}")
                    
                    tokens = await oauth.get_access_token(
                        oauth2_code=code,
                        code_verifier=code_verifier
                    )
                    success = True
            else:
                # LinkedIn and other OAuth 2.0-only platforms
                oauth_handler = await get_oauth_handler(platform)
                
                if not code or not state:
                    return create_html_response(
                        error="Missing OAuth parameters",
                        platform=platform,
                        version=version,
                        auto_close=True
                    )
                
                # Verify state
                logger.info(f"Attempting to verify state: {state}")
                state_data = oauth_handler.verify_state(state)
                if not state_data:
                    return create_html_response(
                        error="Invalid state",
                        platform=platform,
                        version=version,
                        auto_close=True
                    )
                
                logger.info(f"State verification successful. State data: {state_data}")
                user_id = state_data['user_id']
                logger.info(f"Processing callback for user_id: {user_id}")
                
                try:
                    # Exchange code for tokens
                    tokens = await oauth_handler.get_access_token(code)
                    
                    # Generate and store API key
                    api_key = generate_api_key()
                    
                    # Store API key in external service
                    api_key_storage = APIKeyStorage()
                    stored = await api_key_storage.store_api_key(
                        user_id=user_id,
                        platform="linkedin",
                        api_key=api_key,
                        access_token=tokens['access_token'],
                        refresh_token=tokens.get('refresh_token'),
                        expires_in=tokens.get('expires_in', 3600)
                    )
                    
                    if not stored:
                        raise ValueError("Failed to store API key")
                    
                    logger.info(f"Successfully stored API key for user {user_id}")
                    success = True
                    
                except Exception as e:
                    logger.error(f"Error exchanging code for tokens: {str(e)}")
                    return create_html_response(
                        error=str(e),
                        platform=platform,
                        version=version,
                        auto_close=True
                    )
            
            # Return success response
            return create_html_response(
                platform=platform,
                version=version,
                auto_close=True,
                success=success
            )
            
        except Exception as e:
            logger.error(f"Error processing {platform} callback: {str(e)}")
            return create_html_response(
                error=str(e),
                platform=platform,
                version=version,
                auto_close=True
            )
            
    except Exception as e:
        logger.error(f"Callback error: {str(e)}")
        return create_html_response(
            error=str(e),
            platform=platform,
            version=version,
            auto_close=True
        )

# Add a new route specifically for LinkedIn callbacks
@callback_router.get("/linkedin/callback")
async def linkedin_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
) -> HTMLResponse:
    """Handle LinkedIn OAuth callback"""
    try:
        logger.info("Received LinkedIn callback")
        logger.info(f"Code present: {bool(code)}")
        logger.info(f"State present: {bool(state)}")
        
        if error:
            logger.error(f"OAuth error: {error}")
            logger.error(f"Error description: {error_description}")
            return create_html_response(
                error=error_description or error,
                platform="linkedin",
                auto_close=True
            )

        if not code or not state:
            return create_html_response(
                error="Missing OAuth parameters",
                platform="linkedin",
                auto_close=True
            )
        
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
            
            # Generate and store API key
            api_key = generate_api_key()
            
            # Store API key in external service
            api_key_storage = APIKeyStorage()
            stored = await api_key_storage.store_api_key(
                user_id=user_id,
                platform="linkedin",
                api_key=api_key,
                access_token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                expires_in=tokens.get('expires_in', 3600)
            )
            
            if not stored:
                raise ValueError("Failed to store API key")
            
            logger.info(f"Successfully stored API key for user {user_id}")
            success = True
            
            # Return success response with code and state for frontend
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
                            code: '{code}',
                            state: '{state}',
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