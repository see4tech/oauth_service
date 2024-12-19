from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, Dict
from ..core import TokenManager
from ..utils.logger import get_logger
from .oauth_routes import get_oauth_handler, get_code_verifier
import json
import os
import base64
import secrets
import aiohttp
from datetime import datetime, timedelta

logger = get_logger(__name__)
callback_router = APIRouter()

def generate_api_key() -> str:
    """Generate a secure API key."""
    return f"user_{secrets.token_urlsafe(32)}"

async def store_api_key(user_id: str, platform: str, token_data: Dict):
    """Store API key in external storage service."""
    storage_url = os.getenv("API_KEY_STORAGE")
    api_key = os.getenv("API_KEY")
    
    if not storage_url or not api_key:
        raise ValueError("API_KEY_STORAGE or API_KEY not configured")

    # Generate new API key
    user_api_key = generate_api_key()

    # Prepare expiration based on platform
    token_expiration = None
    if platform == "twitter" and "oauth2" in token_data:
        token_expiration = token_data["oauth2"].get("expires_at")
    elif platform == "linkedin":
        token_expiration = token_data.get("expires_at")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                storage_url,
                json={
                    "user_id": user_id,
                    "platform": platform,
                    "api_key": user_api_key,
                    "token_expiration": token_expiration
                },
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key
                }
            ) as response:
                if not response.ok:
                    raise ValueError(f"Failed to store API key: {await response.text()}")
                return await response.json()
    except Exception as e:
        logger.error(f"Error storing API key: {str(e)}")
        raise

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
        state_data = oauth_handler.verify_state(state)
        
        if not state_data:
            logger.error(f"Invalid state parameter. Received state: {state}")
            return create_html_response(error="Invalid state parameter", platform=platform)

        logger.info(f"State verification successful. State data: {state_data}")

        user_id = state_data['user_id']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        token_manager = TokenManager()
        
        # Handle platform-specific token exchange
        try:
            if platform == "twitter":
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
            
            # Store API key in external service
            await store_api_key(user_id, platform, token_data)

            # Return simplified success response
            message_data = {
                "success": True,
                "user_id": user_id,
                "platform": platform
            }

            return create_html_response(
                platform=platform,
                message_data=message_data
            )

        except Exception as e:
            logger.error(f"Error during token exchange for {platform}: {str(e)}")
            return create_html_response(
                error=f"Error during token exchange: {str(e)}",
                platform=platform
            )

    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        return create_html_response(error=str(e), platform=platform)

def create_html_response(
    platform: Optional[str] = None,
    message_data: Optional[Dict] = None,
    error: Optional[str] = None
) -> HTMLResponse:
    """Create HTML response that posts message to opener window."""
    
    if error:
        message_data = {
            "success": False,
            "error": error,
            "platform": platform
        }

    # Convert message_data to JSON string
    message_json = json.dumps(message_data)

    # Create a nonce
    nonce = base64.b64encode(os.urandom(16)).decode('utf-8')

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Status</title>
            <meta http-equiv="Content-Security-Policy" 
                  content="default-src 'self'; script-src 'nonce-{nonce}' 'unsafe-inline'; style-src 'unsafe-inline'">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    background-color: #f8f9fa;
                    color: #212529;
                }}
                .container {{
                    text-align: center;
                    padding: 2rem;
                    background: white;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    max-width: 400px;
                    width: 90%;
                }}
                .icon {{
                    font-size: 48px;
                    margin-bottom: 1rem;
                }}
                .message {{
                    margin-bottom: 1rem;
                }}
                .timer {{
                    color: #6c757d;
                    font-size: 0.9rem;
                }}
                .success {{
                    color: #28a745;
                }}
                .error {{
                    color: #dc3545;
                }}
            </style>
            <script nonce="{nonce}">
                const messageData = {message_json};
                
                function startCountdown() {{
                    const timerElement = document.getElementById('timer');
                    let timeLeft = 5;
                    
                    function updateTimer() {{
                        if (timerElement) {{
                            timerElement.textContent = `Window will close in ${{timeLeft}} seconds...`;
                        }}
                        
                        if (timeLeft <= 0) {{
                            try {{
                                if (window.opener) {{
                                    window.opener.postMessage(messageData, window.location.origin);
                                    window.close();
                                }} else {{
                                    window.location.href = window.location.origin;
                                }}
                            }} catch (e) {{
                                console.error('Error posting message:', e);
                                window.location.href = window.location.origin;
                            }}
                            return;
                        }}
                        
                        timeLeft--;
                        setTimeout(updateTimer, 1000);
                    }}
                    
                    updateTimer();
                }}

                window.onload = startCountdown;
            </script>
        </head>
        <body>
            <div class="container">
                {'<div class="icon error">❌</div>' if error else '<div class="icon success">✅</div>'}
                <h2 class="message {'error' if error else 'success'}">
                    {error if error else f'Successfully authenticated with {platform.title()}!'}
                </h2>
                <p id="timer" class="timer">Window will close in 5 seconds...</p>
            </div>
        </body>
        </html>
    """
    
    headers = {
        'Content-Security-Policy': f"default-src 'self'; script-src 'nonce-{nonce}' 'unsafe-inline'; style-src 'unsafe-inline'"
    }
    
    return HTMLResponse(content=html_content, headers=headers)