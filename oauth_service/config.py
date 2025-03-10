from pydantic_settings import BaseSettings
from typing import Dict, List, Optional
from dotenv import load_dotenv
from functools import lru_cache
import os

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    # Server Configuration
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    ALLOWED_ORIGINS: str = "*"
    WORKERS: int = 4
    
    # Security
    SECRET_KEY: str
    ENCRYPTION_KEY: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    API_KEY: Optional[str] = None
    API_KEY_STORAGE: str  # URL for API key storage service
    
    # Database
    DATABASE_PATH: str = "data/oauth.db"
    
    # OAuth Credentials
    # Twitter
    TWITTER_CLIENT_ID: str           # OAuth 2.0
    TWITTER_CLIENT_SECRET: str       # OAuth 2.0
    TWITTER_CONSUMER_KEY: str        # OAuth 1.0a
    TWITTER_CONSUMER_SECRET: str     # OAuth 1.0a
    TWITTER_CALLBACK_URL: str
    
    # LinkedIn
    LINKEDIN_CLIENT_ID: str
    LINKEDIN_CLIENT_SECRET: str
    LINKEDIN_CALLBACK_URL: str
    
    # Instagram
    INSTAGRAM_CLIENT_ID: str
    INSTAGRAM_CLIENT_SECRET: str
    INSTAGRAM_CALLBACK_URL: str
    
    # Facebook
    FACEBOOK_CLIENT_ID: str
    FACEBOOK_CLIENT_SECRET: str
    FACEBOOK_CALLBACK_URL: str
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 3600
    LINKEDIN_RATE_LIMIT: float = 1.67  # 100 requests per minute = 1.67 requests per second
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "oauth_service.log"
    
    # Frontend URLs (comma-separated)
    FRONTEND_URLS: str  # Required environment variable, no default
    
    @property
    def frontend_origins(self) -> List[str]:
        """Get list of allowed frontend origins."""
        return [url.strip() for url in self.FRONTEND_URLS.split(',')]

    @property
    def oauth_credentials(self) -> Dict:
        """Get all OAuth credentials organized by platform."""
        return {
            "twitter": {
                "client_id": self.TWITTER_CLIENT_ID,
                "client_secret": self.TWITTER_CLIENT_SECRET,
                "consumer_key": self.TWITTER_CONSUMER_KEY,        # OAuth 1.0a
                "consumer_secret": self.TWITTER_CONSUMER_SECRET,  # OAuth 1.0a
                "callback_url": self.TWITTER_CALLBACK_URL
            },
            "linkedin": {
                "client_id": self.LINKEDIN_CLIENT_ID,
                "client_secret": self.LINKEDIN_CLIENT_SECRET,
                "callback_url": self.LINKEDIN_CALLBACK_URL
            },
            "instagram": {
                "client_id": self.INSTAGRAM_CLIENT_ID,
                "client_secret": self.INSTAGRAM_CLIENT_SECRET,
                "callback_url": self.INSTAGRAM_CALLBACK_URL
            },
            "facebook": {
                "client_id": self.FACEBOOK_CLIENT_ID,
                "client_secret": self.FACEBOOK_CLIENT_SECRET,
                "callback_url": self.FACEBOOK_CALLBACK_URL
            }
        }

    def get_platform_credentials(self, platform: str) -> Dict:
        """Get credentials for a specific platform."""
        creds = self.oauth_credentials.get(platform)
        if not creds:
            raise ValueError(f"No credentials found for platform: {platform}")
        return creds

    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins as list."""
        if self.ENVIRONMENT == "development":
            return ["*"]
        else:
            origins = self.ALLOWED_ORIGINS.split(",")
            required_origins = [
                "https://33d10367-52d6-4ff5-99d8-1c6792f179e5.lovableproject.com",
                "https://n8n.see4.tech",
                "https://summarizr.app",
                "https://dukat.see4.tech",
                "http://localhost:3000",
                "http://localhost:8000"
            ]
            return list(set(origins + required_origins))

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "validate_default": True
    }

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    if settings.ENVIRONMENT not in ["development", "production", "testing"]:
        raise ValueError("Invalid environment")
    if settings.ENVIRONMENT == "production":
        if not settings.API_KEY:
            raise ValueError("API_KEY must be set in production")
        if not settings.SECRET_KEY:
            raise ValueError("SECRET_KEY must be set in production")
    return settings
