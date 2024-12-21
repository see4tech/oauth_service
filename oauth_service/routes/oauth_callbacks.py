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

@callback_router.get("/{platform}/callback")
async def oauth_callback(
    request: Request,
    platform: str,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
) -> HTMLResponse:
    """Handle OAuth callback from providers"""
    try:
        logger.info(f"Received callback for platform: {platform}")
        logger.info(f"Code present: {bool(code)}")
        logger.info(f"State present: {bool(state)}")
        
        # Handle OAuth errors
        if error:
            logger.error(f"OAuth error: {error}")
            logger.error(f"Error description: {error_description}")
            return create_html_response(error=error_description or error, platform=platform)

        # For Twitter OAuth 1.0a, we don't get a code parameter
        oauth1_verifier = request.query_params.get('oauth_verifier')
        if not (code or oauth1_verifier) or not state:
            logger.error("Missing required parameters")
            return create_html_response(error="Missing required parameters", platform=platform)

        oauth_handler = await get_oauth_handler(platform)
        
        # Log the state before verification
        logger.info(f"Attempting to verify state: {state}")
        
        state_data = oauth_handler.verify_state(state)
        
        if not state_data:
            logger.error("Invalid state")
            return create_html_response(error="Invalid state", platform=platform)

        logger.info(f"State verification successful. State data: {state_data}")
        user_id = state_data['user_id']
        frontend_callback_url = state_data['frontend_callback_url']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        token_manager = TokenManager()
        
        # For Twitter, handle OAuth 1.0a and 2.0 separately
        if platform == "twitter":
            try:
                if oauth1_verifier:
                    logger.debug("Processing OAuth 1.0a callback")
                    token_data = await oauth_handler.get_access_token(
                        oauth1_verifier=oauth1_verifier
                    )
                    if not token_data or 'oauth1' not in token_data:
                        logger.error("Failed to get OAuth 1.0a tokens")
                        return create_html_response(error="Failed to get OAuth 1.0a tokens", platform=platform)
                else:
                    logger.debug("Processing OAuth 2.0 callback")
                    code_verifier = await get_code_verifier(state)
                    if not code_verifier:
                        logger.error("Code verifier not found")
                        return create_html_response(error="Code verifier not found", platform=platform)
                    
                    token_data = await oauth_handler.get_access_token(
                        oauth2_code=code,
                        code_verifier=code_verifier
                    )
                    if not token_data or 'oauth2' not in token_data:
                        logger.error("Failed to get OAuth 2.0 tokens")
                        return create_html_response(error="Failed to get OAuth 2.0 tokens", platform=platform)
                
                # Store token data
                await token_manager.store_token(
                    platform=platform,
                    user_id=user_id,
                    token_data=token_data
                )
                logger.debug(f"Successfully stored tokens with structure: {list(token_data.keys())}")
                
            except Exception as e:
                logger.error(f"Error processing Twitter callback: {str(e)}")
                return create_html_response(error=str(e), platform=platform)
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
            db.store_user_api_key(user_id, platform, user_api_key)
            logger.info(f"Stored API key locally for user {user_id} on platform {platform}")
            
            # Store in external service if configured
            settings = get_settings()
            storage_url = settings.API_KEY_STORAGE
            api_key = settings.API_KEY
            
            if storage_url and api_key:
                async with aiohttp.ClientSession() as session:
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
        return create_html_response(platform=platform)
        
    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        return create_html_response(error=str(e), platform=platform)

def create_html_response(
    error: Optional[str] = None,
    platform: Optional[str] = None
) -> HTMLResponse:
    """Create HTML response for OAuth callback"""
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>{platform.title()} Auth Callback</title>
            <script>
                // Store data that will be used by the main script
                window.oauthData = {{
                    code: new URLSearchParams(window.location.search).get('code'),
                    state: new URLSearchParams(window.location.search).get('state'),
                    oauth_verifier: new URLSearchParams(window.location.search).get('oauth_verifier'),
                    oauth_token: new URLSearchParams(window.location.search).get('oauth_token'),
                    error: new URLSearchParams(window.location.search).get('error'),
                    error_description: new URLSearchParams(window.location.search).get('error_description'),
                    platform: '{platform.upper()}'
                }};

                function closeWindow() {{
                    // Send message to opener and close window
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: window.oauthData.platform + '_AUTH_CALLBACK',
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

                // Start countdown
                let timeLeft = 10;
                function updateCountdown() {{
                    const countdownElement = document.getElementById('countdown');
                    if (countdownElement) {{
                        countdownElement.textContent = timeLeft;
                        if (timeLeft > 0) {{
                            timeLeft--;
                            setTimeout(updateCountdown, 1000);
                        }} else {{
                            closeWindow();
                        }}
                    }}
                }}

                // Initialize when page loads
                window.onload = function() {{
                    // Send message immediately
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: window.oauthData.platform + '_AUTH_CALLBACK',
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
                .button {{
                    background-color: #3B82F6;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    cursor: pointer;
                    margin-top: 16px;
                }}
                .button:hover {{
                    background-color: #2563EB;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="{error and 'error' or 'success'}">
                    {error and 'Authentication Error' or 'Authentication Successful'}
                </h2>
                <p>{error or 'Authorization successful! You can close this window.'}</p>
                <p>This window will close in <span id="countdown">10</span> seconds</p>
                <button class="button" onclick="closeWindow()">Close Window Now</button>
            </div>
        </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)