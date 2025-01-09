from typing import Optional, Dict
from fastapi import HTTPException
from ..core.oauth_base import OAuthBase
from ..platforms.twitter import TwitterOAuth
from ..platforms.linkedin import LinkedInOAuth
from ..platforms.facebook import FacebookOAuth
from ..platforms.instagram import InstagramOAuth
from ..utils.logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)

async def get_oauth_handler(platform: str, callback_url: Optional[str] = None) -> OAuthBase:
    """Get OAuth handler for specified platform."""
    try:
        settings = get_settings()
        
        if platform == "twitter":
            return TwitterOAuth(
                client_id=settings.TWITTER_CLIENT_ID,
                client_secret=settings.TWITTER_CLIENT_SECRET,
                consumer_key=settings.TWITTER_CONSUMER_KEY,
                consumer_secret=settings.TWITTER_CONSUMER_SECRET,
                callback_url=callback_url or settings.TWITTER_CALLBACK_URL
            )
        elif platform == "linkedin":
            return LinkedInOAuth(
                client_id=settings.LINKEDIN_CLIENT_ID,
                client_secret=settings.LINKEDIN_CLIENT_SECRET,
                callback_url=callback_url or settings.LINKEDIN_CALLBACK_URL
            )
        elif platform == "facebook":
            return FacebookOAuth(
                client_id=settings.FACEBOOK_CLIENT_ID,
                client_secret=settings.FACEBOOK_CLIENT_SECRET,
                callback_url=callback_url or settings.FACEBOOK_CALLBACK_URL
            )
        else:
            raise ValueError(f"Unsupported platform: {platform}")
            
    except Exception as e:
        logger.error(f"Error getting OAuth handler for {platform}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize {platform} OAuth handler: {str(e)}"
        )

# Code verifier storage (temporary in-memory solution)
_code_verifiers = {}

async def store_code_verifier(state: str, code_verifier: str):
    """Store code verifier in temporary storage."""
    _code_verifiers[state] = code_verifier

async def get_code_verifier(state: str) -> Optional[str]:
    """Retrieve code verifier from storage."""
    return _code_verifiers.get(state) 

async def validate_api_keys(user_id: str, platform: str, x_api_key: str) -> bool:
    """Validate API keys for a user."""
    try:
        logger.debug("\n=== validate_api_keys function ===")
        logger.debug(f"User ID: {user_id}")
        logger.debug(f"Platform: {platform}")
        logger.debug(f"Received x-api-key: {x_api_key}")
        
        db = SqliteDB()
        stored_key = db.get_user_api_key(user_id, f"{platform}-oauth1")
        logger.debug(f"Stored key from DB: {stored_key}")
        
        if not stored_key or stored_key != x_api_key:
            logger.debug("API key validation failed!")
            logger.debug(f"Keys match: {stored_key == x_api_key}")
            raise HTTPException(status_code=401, detail="Invalid API key")
            
        return True
        
    except Exception as e:
        logger.error(f"Error in validate_api_keys: {str(e)}")
        raise 