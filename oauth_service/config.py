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
    
    # Database
    DATABASE_PATH: str = "data/oauth.db"
    
    # OAuth Credentials
    # Twitter
    TWITTER_CLIENT_ID: str
    TWITTER_CLIENT_SECRET: str
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
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "oauth_service.log"

    @property
    def oauth_credentials(self) -> Dict:
        """Get all OAuth credentials organized by platform."""
        return {
            "twitter": {
                "client_id": self.TWITTER_CLIENT_ID,
                "client_secret": self.TWITTER_CLIENT_SECRET,
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

    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins as list."""
        if self.ENVIRONMENT == "development":
            return ["*"]
        else:
            origins = self.ALLOWED_ORIGINS.split(",")
            # Ensure we have at least these origins
            required_origins = [
                "https://33d10367-52d6-4ff5-99d8-1c6792f179e5.lovableproject.com",
                "https://dukat.see4.tech",
                "http://localhost:3000",
                "http://localhost:8000"
            ]
            return list(set(origins + required_origins))

    def get_platform_credentials(self, platform: str) -> Dict:
        """Get credentials for a specific platform."""
        creds = self.oauth_credentials.get(platform)
        if not creds:
            raise ValueError(f"No credentials found for platform: {platform}")
        return creds

    # class Config:
    #     env_file = ".env"
    #     case_sensitive = True
        
    #     # Example validation
    #     @classmethod
    #     def validate_all(cls, settings: "Settings") -> None:
    #         """Validate all settings."""
    #         # Validate environment
    #         if settings.ENVIRONMENT not in ["development", "production", "testing"]:
    #             raise ValueError("Invalid environment")
                
    #         # Validate required security settings in production
    #         if settings.ENVIRONMENT == "production":
    #             if not settings.API_KEY:
    #                 raise ValueError("API_KEY must be set in production")
    #             if not settings.SECRET_KEY:
    #                 raise ValueError("SECRET_KEY must be set in production")
    class Config:
        env_file = ".env"
        case_sensitive = True
        
        @classmethod
        def validate_default(cls, settings: "Settings") -> None:
            if settings.ENVIRONMENT not in ["development", "production", "testing"]:
                raise ValueError("Invalid environment")
                
            if settings.ENVIRONMENT == "production":
                if not settings.API_KEY:
                    raise ValueError("API_KEY must be set in production")
                if not settings.SECRET_KEY:
                    raise ValueError("SECRET_KEY must be set in production")

# Create cached settings instance
@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    settings.Config.validate_all(settings)
    return settings
