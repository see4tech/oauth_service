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
    """Handle OAuth callback from providers"""
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
                auto_close=True  # Auto close on error
            )

        # Get OAuth 1.0a parameters
        oauth_token = request.query_params.get('oauth_token')
        oauth_verifier = request.query_params.get('oauth_verifier')
        
        success = False
        try:
            if version == "1":
                # OAuth 1.0a flow
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
                # OAuth 2.0 flow
                if not code or not state:
                    return create_html_response(
                        error="Missing OAuth 2.0 parameters",
                        platform=platform,
                        version=version,
                        auto_close=True
                    )
                # Process OAuth 2.0...
                success = True
                
            return create_html_response(
                platform=platform,
                version=version,
                auto_close=True,  # Auto close on success
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

def create_html_response(
    error: Optional[str] = None,
    platform: Optional[str] = None,
    version: Optional[str] = None,
    auto_close: bool = False,
    success: bool = False
) -> HTMLResponse:
    """Create HTML response for OAuth callback."""
    
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
                            type: 'TWITTER_AUTH_CALLBACK',
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