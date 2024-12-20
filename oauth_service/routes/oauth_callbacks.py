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
            error_msg = error_description or error
            logger.error(f"OAuth error for {platform}: {error_msg}")
            return create_html_response(error=error_msg, platform=platform)

        if not code or not state:
            logger.error("Missing code or state parameter")
            return create_html_response(error="Missing code or state parameter", platform=platform)

        oauth_handler = await get_oauth_handler(platform)
        
        # Log the state before verification
        logger.info(f"Attempting to verify state: {state}")
        
        state_data = oauth_handler.verify_state(state)
        
        if not state_data:
            logger.error(f"Invalid state parameter. Received state: {state}")
            return create_html_response(error="Invalid state parameter", platform=platform)

        logger.info(f"State verification successful. State data: {state_data}")
        user_id = state_data['user_id']
        frontend_callback_url = state_data['frontend_callback_url']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        token_manager = TokenManager()
        
        # Handle Twitter OAuth 2.0 with PKCE
        if platform == "twitter":
            # Retrieve code verifier
            code_verifier = await get_code_verifier(state)
            if not code_verifier:
                logger.error("Code verifier not found for Twitter OAuth")
                return create_html_response(error="Code verifier not found", platform=platform)
                
            token_data = await oauth_handler.get_access_token(
                oauth2_code=code,
                code_verifier=code_verifier
            )
        else:
            token_data = await oauth_handler.get_access_token(code)
            
        await token_manager.store_token(platform, user_id, token_data)
        
        # Store API key in external storage service
        settings = get_settings()
        storage_url = settings.API_KEY_STORAGE
        api_key = settings.API_KEY
        
        if storage_url and api_key:
            try:
                # Generate API key
                user_api_key = generate_api_key()
                
                # Store API key locally first
                db = SqliteDB()
                db.store_user_api_key(user_id, platform, user_api_key)
                logger.info(f"Stored API key locally for user {user_id} on platform {platform}")
                
                # Then store in external service
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
        else:
            logger.error("API_KEY_STORAGE or API_KEY not configured")
        
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
    # Generate nonces for script and style
    script_nonce = secrets.token_urlsafe(16)
    style_nonce = secrets.token_urlsafe(16)
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>{platform.title()} Auth Callback</title>
            <style nonce="{style_nonce}">
                body {{
                    font-family: Arial, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f5f5f5;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    background-color: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                    max-width: 80%;
                }}
                .success {{
                    color: #4CAF50;
                }}
                .error {{
                    color: #f44336;
                }}
                .message {{
                    margin-bottom: 1rem;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h2 class="{error and 'error' or 'success'}">
                    {error and 'Authentication Error' or 'Authentication Successful'}
                </h2>
                <p class="message">
                    {error or 'You can close this window now.'}
                </p>
                <p class="message">
                    <small>Debug info: code={'{code}'}, state={'{state}'}</small>
                </p>
            </div>
            
            <script nonce="{script_nonce}">
                function getQueryParam(param) {{
                    const urlParams = new URLSearchParams(window.location.search);
                    return urlParams.get(param);
                }}

                const code = getQueryParam('code');
                const state = getQueryParam('state');
                const error = getQueryParam('error');
                const error_description = getQueryParam('error_description');

                const message = {{
                    type: '{platform.upper()}_AUTH_CALLBACK',
                    code,
                    state,
                    error: error_description || error || {json.dumps(error)}
                }};

                console.log('Sending message to opener:', message);

                if (window.opener) {{
                    window.opener.postMessage(message, '*');
                    console.log('Message posted to opener window');
                    setTimeout(() => {{
                        console.log('Closing window...');
                        window.close();
                    }}, 2000);
                }} else {{
                    console.error('No opener window found');
                }}
            </script>
        </body>
    </html>
    """
    
    # Set response headers with nonce-based CSP
    headers = {
        'Content-Security-Policy': (
            f"default-src 'none'; "
            f"script-src 'nonce-{script_nonce}'; "
            f"style-src 'nonce-{style_nonce}'; "
            "connect-src *"
        )
    }
    
    return HTMLResponse(content=html_content, headers=headers)