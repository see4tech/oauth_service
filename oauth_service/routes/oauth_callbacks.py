from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from typing import Optional
from ..core import TokenManager
from ..utils.logger import get_logger
from .oauth_routes import get_oauth_handler

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
) -> RedirectResponse:
    try:
        # Handle OAuth errors
        if error:
            error_msg = error_description or error
            logger.error(f"OAuth error for {platform}: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state parameter")

        oauth_handler = await get_oauth_handler(platform)
        state_data = oauth_handler.verify_state(state)

        if not state_data:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        user_id = state_data['user_id']
        frontend_callback_url = state_data['frontend_callback_url']

        token_manager = TokenManager()
        token_data = await oauth_handler.get_access_token(code)
        await token_manager.store_token(platform, user_id, token_data)

        # Construct success URL with authorization code
        success_url = (
            f"{frontend_callback_url}"
            f"?platform={platform}"
            f"&status=success"
            f"&code={code}"
            f"&state={state}"
        )
        
        return RedirectResponse(url=success_url)

    except Exception as e:
        logger.error(f"Error handling OAuth callback for {platform}: {str(e)}")
        error_url = (
            f"{frontend_callback_url if 'frontend_callback_url' in locals() else request.base_url}"
            f"?platform={platform}"
            f"&status=error"
            f"&message={str(e)}"
        )
        return RedirectResponse(url=error_url)