from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict
from datetime import datetime

class OAuthInitRequest(BaseModel):
    """Request model for initializing OAuth flow."""
    user_id: str
    redirect_uri: HttpUrl
    frontend_callback_url: HttpUrl
    scopes: Optional[List[str]] = None

class OAuthInitResponse(BaseModel):
    """Response model for OAuth initialization."""
    authorization_url: str
    state: str
    platform: str
    additional_params: Optional[Dict] = None

class OAuthCallbackRequest(BaseModel):
    """Request model for OAuth callback."""
    code: str
    state: str
    redirect_uri: HttpUrl
    oauth1_verifier: Optional[str] = None  # For Twitter OAuth 1.0a

class TokenResponse(BaseModel):
    """Response model for OAuth tokens."""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 0  # 0 for OAuth 1.0a tokens that don't expire
    refresh_token: Optional[str] = None
    scope: Optional[str] = None
    access_token_secret: Optional[str] = None  # For OAuth 1.0a tokens
    created_at: datetime = Field(default_factory=datetime.utcnow)
    oauth1_url: Optional[str] = None  # For Twitter OAuth 1.0a URL
    success: bool = True  # Indicate if the token exchange was successful

class PostContent(BaseModel):
    """Request model for creating social media posts."""
    text: str
    media_urls: Optional[List[HttpUrl]] = None
    link: Optional[HttpUrl] = None
    additional_params: Optional[Dict] = None

class PostResponse(BaseModel):
    """Response model for created posts."""
    post_id: str
    platform: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    url: Optional[HttpUrl] = None
    platform_specific_data: Optional[Dict] = None

class MediaUploadResponse(BaseModel):
    """Response model for media uploads."""
    media_id: str
    media_type: str
    url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None

class UserProfile(BaseModel):
    """Model for user profile data."""
    id: str
    platform: str
    username: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    profile_url: Optional[HttpUrl] = None
    avatar_url: Optional[HttpUrl] = None
    raw_data: Optional[Dict] = None