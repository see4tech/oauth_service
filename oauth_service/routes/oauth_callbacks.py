from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, Dict
from ..core import TokenManager
from ..utils.logger import get_logger
from .oauth_routes import get_oauth_handler, get_code_verifier
from ..core.db import SqliteDB
from ..config import get_settings
import json
import os
import base64
import secrets
import aiohttp
from datetime import datetime

logger = get_logger(__name__)
callback_router = APIRouter()

def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"user_{secrets.token_urlsafe(32)}"

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
    """Handle OAuth callback from providers"""
    try:
        logger.info(f"Received callback for platform: {platform}, version: {version}")
        logger.info(f"Code present: {bool(code)}")
        logger.info(f"State present: {bool(state)}")
        
        # Handle OAuth errors
        if error:
            logger.error(f"OAuth error: {error}")
            logger.error(f"Error description: {error_description}")
            return create_html_response(error=error_description or error, platform=platform, version=version)

        # Get OAuth 1.0a parameters
        oauth_token = request.query_params.get('oauth_token')
        oauth_verifier = request.query_params.get('oauth_verifier')
        
        # For OAuth 1.0a, we need oauth_token and oauth_verifier
        if version == "1":
            if not oauth_token or not oauth_verifier:
                logger.error("Missing OAuth 1.0a parameters")
                return create_html_response(error="Missing OAuth 1.0a parameters", platform=platform, version=version)
            
            # For OAuth 1.0a, we don't need to verify state as Twitter doesn't return it
            state_data = {
                'user_id': request.query_params.get('user_id'),
                'frontend_callback_url': request.query_params.get('frontend_callback_url')
            }
            if not state_data['user_id'] or not state_data['frontend_callback_url']:
                logger.error("Missing user_id or frontend_callback_url in OAuth 1.0a callback")
                return create_html_response(error="Missing user information", platform=platform, version=version)
        # For OAuth 2.0, we need code and state
        else:
            if not code or not state:
                logger.error("Missing OAuth 2.0 parameters")
                return create_html_response(error="Missing OAuth 2.0 parameters", platform=platform, version=version)
            
            oauth_handler = await get_oauth_handler(platform)
            # Log the state before verification
            logger.info(f"Attempting to verify state: {state}")
            state_data = oauth_handler.verify_state(state)
            if not state_data:
                logger.error("Invalid state")
                return create_html_response(error="Invalid state", platform=platform, version=version)

        logger.info(f"State verification successful. State data: {state_data}")
        user_id = state_data['user_id']
        frontend_callback_url = state_data['frontend_callback_url']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        token_manager = TokenManager()
        
        # For Twitter, handle OAuth 1.0a and 2.0 separately
        if platform == "twitter":
            try:
                # Get OAuth 1.0a parameters
                oauth_token = request.query_params.get('oauth_token')
                oauth1_verifier = request.query_params.get('oauth_verifier')

                if version == "1" and oauth_token and oauth1_verifier:
                    logger.debug("Processing OAuth 1.0a callback")
                    logger.debug(f"OAuth 1.0a parameters: token={oauth_token}, verifier={oauth1_verifier}")
                    
                    # Create new OAuth handler for this request
                    oauth_handler = TwitterOAuth(
                        client_id=os.getenv("TWITTER_CLIENT_ID"),
                        client_secret=os.getenv("TWITTER_CLIENT_SECRET"),
                        callback_url=os.getenv("TWITTER_CALLBACK_URL"),
                        consumer_key=os.getenv("TWITTER_CONSUMER_KEY"),
                        consumer_secret=os.getenv("TWITTER_CONSUMER_SECRET")
                    )
                    
                    # Set up the request token
                    oauth_handler.oauth1_handler.request_token = {
                        'oauth_token': oauth_token,
                        'oauth_token_secret': ''  # This is okay for the verification step
                    }
                    
                    token_data = await oauth_handler.get_access_token(
                        oauth1_verifier=oauth1_verifier
                    )
                    if not token_data or 'oauth1' not in token_data:
                        logger.error("Failed to get OAuth 1.0a tokens")
                        return create_html_response(error="Failed to get OAuth 1.0a tokens", platform=platform, version=version)
                elif version == "2" and code:
                    logger.debug("Processing OAuth 2.0 callback")
                    code_verifier = await get_code_verifier(state)
                    if not code_verifier:
                        logger.error("Code verifier not found")
                        return create_html_response(error="Code verifier not found", platform=platform, version=version)
                    
                    token_data = await oauth_handler.get_access_token(
                        oauth2_code=code,
                        code_verifier=code_verifier
                    )
                    
                    # Validate OAuth 2.0 token data
                    if not token_data or 'oauth2' not in token_data:
                        logger.error("Failed to get OAuth 2.0 tokens")
                        return create_html_response(error="Failed to get OAuth 2.0 tokens", platform=platform, version=version)
                    
                    # Log OAuth 2.0 token structure
                    oauth2_data = token_data['oauth2']
                    logger.debug(f"OAuth 2.0 token data structure: {list(oauth2_data.keys())}")
                    logger.debug(f"Has refresh_token: {bool(oauth2_data.get('refresh_token'))}")
                    logger.debug(f"Expires in: {oauth2_data.get('expires_in')}")
                    logger.debug(f"Expires at: {datetime.fromtimestamp(oauth2_data.get('expires_at', 0)).strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    if not oauth2_data.get('refresh_token'):
                        logger.warning("No refresh token received in OAuth 2.0 response. Token data: %s", list(oauth2_data.keys()))
                else:
                    logger.error("Invalid OAuth version or missing parameters")
                    return create_html_response(error="Invalid OAuth version or missing parameters", platform=platform, version=version)
                
                # Store token data
                await token_manager.store_token(
                    platform=platform,
                    user_id=user_id,
                    token_data=token_data
                )
                logger.debug(f"Successfully stored tokens with structure: {list(token_data.keys())}")
                
                # Verify stored tokens
                stored_tokens = await token_manager.get_token(platform, user_id)
                if stored_tokens:
                    logger.debug(f"Verified stored token structure: {list(stored_tokens.keys())}")
                    if 'oauth2' in stored_tokens:
                        logger.debug(f"Verified OAuth 2.0 token keys: {list(stored_tokens['oauth2'].keys())}")
                        logger.debug(f"Stored refresh token present: {bool(stored_tokens['oauth2'].get('refresh_token'))}")
                
            except Exception as e:
                logger.error(f"Error processing Twitter callback: {str(e)}")
                return create_html_response(error=str(e), platform=platform, version=version)
        else:
            # Handle other platforms
            token_data = await oauth_handler.get_access_token(code)
            await token_manager.store_token(platform, user_id, token_data)
        
        # Generate and store API key
        try:
            # Generate API key
            user_api_key = generate_api_key()
            
            # Store API key locally
            db = SqliteDB()
            # For Twitter, use different platform identifiers for OAuth 1.0a and OAuth 2.0
            if platform == "twitter":
                if "oauth1" in token_data:
                    db.store_user_api_key(user_id, "twitter-oauth1", user_api_key)
                    logger.info(f"Stored OAuth 1.0a API key locally for user {user_id}")
                if "oauth2" in token_data:
                    db.store_user_api_key(user_id, "twitter-oauth2", user_api_key)
                    logger.info(f"Stored OAuth 2.0 API key locally for user {user_id}")
            else:
                db.store_user_api_key(user_id, platform, user_api_key)
                logger.info(f"Stored API key locally for user {user_id} on platform {platform}")
            
            # Store in external service if configured
            settings = get_settings()
            storage_url = settings.API_KEY_STORAGE
            api_key = settings.API_KEY
            
            if storage_url and api_key:
                async with aiohttp.ClientSession() as session:
                    # For Twitter, store API key twice with different platform identifiers
                    if platform == "twitter":
                        platforms_to_store = []
                        if "oauth1" in token_data:
                            platforms_to_store.append("twitter-oauth1")
                        if "oauth2" in token_data:
                            platforms_to_store.append("twitter-oauth2")
                        
                        for platform_id in platforms_to_store:
                            async with session.post(
                                f"{storage_url}/store",
                                json={
                                    "user_id": user_id,
                                    "platform": platform_id,
                                    "api_key": user_api_key
                                },
                                headers={
                                    "Content-Type": "application/json",
                                    "x-api-key": api_key
                                }
                            ) as response:
                                if not response.ok:
                                    logger.error(f"Failed to store API key in external service for {platform_id}: {await response.text()}")
                                else:
                                    logger.info(f"Successfully stored API key in external service for user {user_id} on platform {platform_id}")
                    else:
                        async with session.post(
                            f"{storage_url}/store",
                            json={
                                "user_id": user_id,
                                "platform": platform,
                                "api_key": user_api_key
                            },
                            headers={
                                "Content-Type": "application/json",
                                "x-api-key": api_key
                            }
                        ) as response:
                            if not response.ok:
                                logger.error(f"Failed to store API key in external service: {await response.text()}")
                            else:
                                logger.info(f"Successfully stored API key in external service for user {user_id} on platform {platform}")
        except Exception as e:
            logger.error(f"Error storing API key: {str(e)}")
        
        # Return success response
        return create_html_response(platform=platform, version=version)
        
    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        return create_html_response(error=str(e), platform=platform, version=version)

def create_html_response(
    error: Optional[str] = None,
    platform: Optional[str] = None,
    version: Optional[str] = None
) -> HTMLResponse:
    """Create HTML response for OAuth callback."""
    
    html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Callback</title>
            <script>
                window.oauthData = {{
                    platform: {json.dumps(platform)},
                    version: {json.dumps(version)},
                    code: new URLSearchParams(window.location.search).get('code'),
                    state: new URLSearchParams(window.location.search).get('state'),
                    oauth_verifier: new URLSearchParams(window.location.search).get('oauth_verifier'),
                    oauth_token: new URLSearchParams(window.location.search).get('oauth_token'),
                    error_description: new URLSearchParams(window.location.search).get('error_description'),
                    error: {json.dumps(error)}
                }};

                function closeWindow() {{
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'TWITTER_AUTH_CALLBACK',
                            success: !{json.dumps(bool(error))},
                            code: window.oauthData.code,
                            state: window.oauthData.state,
                            oauth_verifier: window.oauthData.oauth_verifier,
                            oauth_token: window.oauthData.oauth_token,
                            error: window.oauthData.error_description || window.oauthData.error || {json.dumps(error)}
                        }}, '*');
                        
                        // Add a delay before closing
                        setTimeout(() => window.close(), 1000);
                    }}
                }}

                // Initialize when page loads
                window.onload = function() {{
                    // Send message immediately
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'TWITTER_AUTH_CALLBACK',
                            success: !{json.dumps(bool(error))},
                            code: window.oauthData.code,
                            state: window.oauthData.state,
                            oauth_verifier: window.oauthData.oauth_verifier,
                            oauth_token: window.oauthData.oauth_token,
                            error: window.oauthData.error_description || window.oauthData.error || {json.dumps(error)}
                        }}, '*');
                    }}
                    // Start countdown after message is sent
                    updateCountdown();
                }};
            </script>
            <style>
                body {{ 
                    font-family: Arial; 
                    text-align: center; 
                    padding-top: 50px;
                    background-color: #f5f5f5;
                }}
                .container {{
                    max-width: 400px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .success {{ color: #10B981; }}
                .error {{ color: #EF4444; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="{error and 'error' or 'success'}">
                    {error and 'Authentication Failed' or 'Authentication Successful'}
                </h2>
                <p>
                    {error or 'You can close this window now.'}
                </p>
                <p>
                    Window will close automatically in <span id="countdown">5</span> seconds.
                </p>
            </div>
        </body>
        </html>
    """
    
    return HTMLResponse(content=html_content)