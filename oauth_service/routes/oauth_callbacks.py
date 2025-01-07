from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, Dict
from ..core import TokenManager
from ..utils.logger import get_logger
from .oauth_routes import get_oauth_handler, get_code_verifier
from ..core.db import SqliteDB
from ..config import get_settings
from ..api.api_key_storage import APIKeyStorage
from ..utils.crypto import generate_api_key
import json
import os
import base64
import aiohttp
from datetime import datetime

logger = get_logger(__name__)
callback_router = APIRouter()

def init_twitter_oauth(user_id: str, frontend_callback_url: str) -> dict:
    """Initialize Twitter OAuth flow."""
    try:
        oauth = TwitterOAuth(
            client_id=settings.TWITTER_CLIENT_ID,
            client_secret=settings.TWITTER_CLIENT_SECRET,
            redirect_uri=settings.TWITTER_CALLBACK_URL + "/2",  # Append /2 for OAuth 2.0
        )
        
        # Generate and encrypt state
        state = generate_oauth_state(
            user_id=user_id,
            frontend_callback_url=frontend_callback_url,
            platform="twitteroauth"
        )
        
        # Get authorization URL WITHOUT passing state parameter
        auth_url = oauth.get_authorization_url()  # Remove state parameter from here
        
        # Manually append state to URL
        separator = '&' if '?' in auth_url else '?'
        auth_url = f"{auth_url}{separator}state={state}"
        
        logger.debug(f"Generated Twitter OAuth URL: {auth_url}")
        
        return {
            "authorization_url": auth_url,
            "state": state
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
                # Get the callback URL that matches what was used in the request
                callback_url = str(request.url).split('?')[0]
                logger.debug(f"Callback URL: {callback_url}")
                
                # Initialize OAuth handler with the same callback URL
                oauth_handler = await get_oauth_handler(platform, callback_url)
                
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
                    tokens = await oauth_handler.get_access_token(
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
                    await api_key_storage.store_api_key(
                        user_id=user_id,
                        platform=platform,
                        api_key=api_key,
                        access_token=tokens['access_token'],
                        refresh_token=tokens.get('refresh_token'),
                        expires_in=tokens.get('expires_in', 3600)
                    )
                    
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
            await api_key_storage.store_api_key(
                user_id=user_id,
                platform="linkedin",
                api_key=api_key,
                access_token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                expires_in=tokens.get('expires_in', 3600)
            )
            
            logger.info(f"Successfully stored API key for user {user_id}")
            success = True
            
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {str(e)}")
            return create_html_response(
                error=str(e),
                platform="linkedin",
                auto_close=True
            )
        
        # Return success response
        return create_html_response(
            platform="linkedin",
            auto_close=True,
            success=success
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
    
    # Determine message type based on platform
    message_type = f"{platform.upper()}_AUTH_CALLBACK" if platform else "OAUTH_CALLBACK"
    
    html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>OAuth Callback</title>
            <script>
                let countdown = 10;
                let countdownInterval;
                let processComplete = {json.dumps(auto_close)};
                
                function closeWindow() {{
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: '{message_type}',
                            success: {json.dumps(success and not error)},
                            error: {json.dumps(error)},
                            platform: {json.dumps(platform)},
                            version: {json.dumps(version)}
                        }}, '*');
                    }}
                    window.close();
                }}
                
                function updateCountdown() {{
                    const countdownElement = document.getElementById('countdown');
                    countdownElement.textContent = countdown;
                    if (countdown <= 0) {{
                        clearInterval(countdownInterval);
                        closeWindow();
                    }}
                    countdown--;
                }}
                
                function cancelAutoClose() {{
                    clearInterval(countdownInterval);
                    document.getElementById('countdown-container').style.display = 'none';
                }}
                
                window.onload = function() {{
                    if (processComplete) {{
                        document.getElementById('status-message').style.display = 'block';
                        document.getElementById('countdown-container').style.display = 'block';
                        document.getElementById('close-button').style.display = 'block';
                        countdownInterval = setInterval(updateCountdown, 1000);
                    }}
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
                .button {{
                    margin: 10px;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 14px;
                }}
                .close-button {{
                    background-color: #3B82F6;
                    color: white;
                    display: none;
                }}
                .cancel-button {{
                    background-color: #6B7280;
                    color: white;
                }}
                #status-message, #countdown-container {{
                    display: none;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="{error and 'error' or 'success'}">
                    {error and 'Authentication Failed' or 'Authentication in Progress...'}
                </h2>
                <div id="status-message">
                    <h2 class="{error and 'error' or 'success'}">
                        {error and 'Authentication Failed' or 'Authentication Successful'}
                    </h2>
                    <p>
                        {error or 'You can close this window now.'}
                    </p>
                </div>
                <div id="countdown-container">
                    <p>
                        Window will close automatically in <span id="countdown">10</span> seconds.
                    </p>
                    <button class="button cancel-button" onclick="cancelAutoClose()">
                        Cancel Auto-Close
                    </button>
                </div>
                <button id="close-button" class="button close-button" onclick="closeWindow()">
                    Close Window Now
                </button>
            </div>
        </body>
        </html>
    """
    
    return HTMLResponse(content=html_content)