# from fastapi import APIRouter, HTTPException, Request
# from fastapi.responses import RedirectResponse
# from typing import Optional
# from ..core import TokenManager
# from ..utils.logger import get_logger
# from .oauth_routes import get_oauth_handler

# logger = get_logger(__name__)
# callback_router = APIRouter()

# @callback_router.get("/{platform}/callback")
# async def oauth_callback(
#     request: Request,
#     platform: str,
#     code: Optional[str] = None,
#     state: Optional[str] = None,
#     error: Optional[str] = None,
#     error_description: Optional[str] = None
# ) -> RedirectResponse:
#     """Handle OAuth callback from providers"""
#     try:
#         logger.info(f"Received callback for platform: {platform}")
#         logger.info(f"Code present: {bool(code)}")
#         logger.info(f"State present: {bool(state)}")
        
#         # Handle OAuth errors
#         if error:
#             error_msg = error_description or error
#             logger.error(f"OAuth error for {platform}: {error_msg}")
#             raise HTTPException(status_code=400, detail=error_msg)

#         if not code or not state:
#             logger.error("Missing code or state parameter")
#             raise HTTPException(status_code=400, detail="Missing code or state parameter")

#         oauth_handler = await get_oauth_handler(platform)
        
#         # Log the state before verification
#         logger.info(f"Attempting to verify state: {state}")
        
#         state_data = oauth_handler.verify_state(state)
        
#         if not state_data:
#             logger.error(f"Invalid state parameter. Received state: {state}")
#             raise HTTPException(status_code=400, detail="Invalid state parameter")

#         logger.info(f"State verification successful. State data: {state_data}")
        
#         user_id = state_data['user_id']
#         frontend_callback_url = state_data['frontend_callback_url']

#         logger.info(f"Processing callback for user_id: {user_id}")
        
#         token_manager = TokenManager()
#         token_data = await oauth_handler.get_access_token(code)
#         await token_manager.store_token(platform, user_id, token_data)

#         success_url = (
#             f"{frontend_callback_url}"
#             f"?platform={platform}"
#             f"&status=success"
#             f"&code={code}"
#             f"&state={state}"
#         )
        
#         logger.info(f"Redirecting to success URL: {success_url}")
#         return RedirectResponse(url=success_url)

#     except Exception as e:
#         logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
#         error_url = (
#             f"{frontend_callback_url if 'frontend_callback_url' in locals() else request.base_url}"
#             f"?platform={platform}"
#             f"&status=error"
#             f"&message={str(e)}"
#         )
#         logger.error(f"Redirecting to error URL: {error_url}")
#         return RedirectResponse(url=error_url)
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional, Dict
from ..core import TokenManager
from ..utils.logger import get_logger
from .oauth_routes import get_oauth_handler
import json

logger = get_logger(__name__)
callback_router = APIRouter()

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
            return create_html_response(error=error_msg)

        if not code or not state:
            logger.error("Missing code or state parameter")
            return create_html_response(error="Missing code or state parameter")

        oauth_handler = await get_oauth_handler(platform)
        
        # Log the state before verification
        logger.info(f"Attempting to verify state: {state}")
        
        state_data = oauth_handler.verify_state(state)
        
        if not state_data:
            logger.error(f"Invalid state parameter. Received state: {state}")
            return create_html_response(error="Invalid state parameter")

        logger.info(f"State verification successful. State data: {state_data}")
        
        user_id = state_data['user_id']
        frontend_callback_url = state_data['frontend_callback_url']
        logger.info(f"Processing callback for user_id: {user_id}")
        
        token_manager = TokenManager()
        token_data = await oauth_handler.get_access_token(code)
        await token_manager.store_token(platform, user_id, token_data)

        # Return HTML that will post a message to the opener window
        return create_html_response(
            code=code,
            state=state,
            platform=platform,
            token_data=token_data
        )

    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        return create_html_response(error=str(e))

def create_html_response(
    code: Optional[str] = None,
    state: Optional[str] = None,
    platform: Optional[str] = None,
    token_data: Optional[Dict] = None,
    error: Optional[str] = None
) -> HTMLResponse:
    """Create HTML response that posts message to opener window."""
    
    if error:
        message_data = {
            "type": "LINKEDIN_AUTH_CALLBACK",
            "error": error
        }
    else:
        message_data = {
            "type": "LINKEDIN_AUTH_CALLBACK",
            "code": code,
            "state": state,
            "platform": platform,
            "token_data": token_data
        }

    # Convert message_data to JSON string
    message_json = json.dumps(message_data)

    html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Processing Authentication</title>
            <script>
                window.onload = function() {{
                    try {{
                        if (window.opener) {{
                            // Post message to opener
                            window.opener.postMessage({message_json}, window.location.origin);
                            // Close this window
                            window.close();
                        }} else {{
                            // If no opener, redirect to origin
                            window.location.href = window.location.origin;
                        }}
                    }} catch (e) {{
                        console.error('Error posting message:', e);
                        window.location.href = window.location.origin;
                    }}
                }};
            </script>
        </head>
        <body>
            <h3>Processing authentication...</h3>
            <p>This window should close automatically. If it doesn't, you may close it.</p>
        </body>
        </html>
    """
    
    return HTMLResponse(content=html_content)