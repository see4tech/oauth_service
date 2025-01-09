from fastapi import FastAPI, Security, HTTPException, Depends, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from starlette.status import HTTP_403_FORBIDDEN
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager
from .routes.oauth_routes import router as oauth_router
from .routes.oauth_callbacks import callback_router
from .config import get_settings
import uvicorn
from datetime import datetime
from .utils.logger import get_logger
from .core.token_refresh import start_refresh_service, stop_refresh_service
import asyncio
from .core.db import SqliteDB
import requests
import json

# Initialize settings and logger
settings = get_settings()
logger = get_logger(__name__)

# API Key security
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # For OAuth callback routes, allow inline scripts and styles
        if request.url.path.startswith('/oauth') and '/callback/' in request.url.path:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self' *; "
                "frame-ancestors 'self'; "
                "img-src 'self' data:; "
                "base-uri 'self'"
            )
        else:
            # For all other routes, set default CSP
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https:; "
                "frame-src 'self' https://www.linkedin.com https://api.linkedin.com; "
                "frame-ancestors 'self'"
            )
        
        # Set other security headers
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("\n=== OAuth Service Startup ===")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"API Key configured: {bool(settings.API_KEY)}")
    print(f"API Key value: {settings.API_KEY}")
    print("===========================\n")
    
    logger.info(f"Starting OAuth Service in {settings.ENVIRONMENT} environment")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API documentation available at: {'/docs' if settings.ENVIRONMENT != 'production' else 'Disabled'}")
    
    # Log configuration
    logger.debug("OAuth Service Configuration:")
    logger.debug(f"Server Host: {settings.SERVER_HOST}")
    logger.debug(f"Server Port: {settings.SERVER_PORT}")
    logger.debug(f"Environment: {settings.ENVIRONMENT}")
    logger.debug(f"Allowed Origins: {settings.ALLOWED_ORIGINS}")
    
    # Log OAuth configurations
    logger.debug("OAuth Configurations:")
    for platform in ['linkedin', 'twitter', 'facebook', 'instagram']:
        creds = settings.oauth_credentials.get(platform, {})
        logger.debug(f"{platform.title()} Configuration:")
        logger.debug(f"- Client ID configured: {'Yes' if creds.get('client_id') else 'No'}")
        logger.debug(f"- Callback URL: {creds.get('callback_url')}")
    
    yield
    
    logger.info("Shutting down OAuth Service")

# At the top, after imports and settings initialization
async def get_api_key(request: Request, api_key_header: str = Security(api_key_header)) -> str:
    """Dependency to validate API key."""
    try:
        # Skip validation for OAuth callbacks and initialization
        if "/callback" in request.url.path or request.url.path.endswith("/init"):
            return api_key_header
            
        # Check if it's a user-specific endpoint
        if request.method == "POST":
            try:
                body = await request.json()
                user_id = body.get("user_id")
                
                if user_id:
                    db = SqliteDB()
                    if "twitter" in request.url.path:
                        stored_key = db.get_user_api_key(user_id, "twitter-oauth1")  # Just check oauth1 since they're the same
                        if api_key_header == stored_key:
                            return api_key_header
                    else:
                        platform = request.url.path.split("/")[2]
                        stored_key = db.get_user_api_key(user_id, platform)
                        if api_key_header == stored_key:
                            return api_key_header
                            
            except json.JSONDecodeError:
                pass
                
        # Only check global API key if no user-specific key matched
        if api_key_header == settings.API_KEY:
            return api_key_header
            
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Could not validate API key"
        )
    except Exception as e:
        logger.error(f"Error in API key validation: {str(e)}")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Could not validate API key"
        )

# Initialize FastAPI app
app = FastAPI(
    title="OAuth Service",
    description="A comprehensive OAuth implementation supporting multiple platforms",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

# Then, add the middleware
@app.middleware("http")
async def validate_api_key(request: Request, call_next):
    """Validate API key from header."""
    try:
        # Skip validation for OAuth callbacks and initialization
        if "/callback" in request.url.path or request.url.path.endswith("/init"):
            return await call_next(request)
        
        # Get API key from header
        api_key = request.headers.get("x-api-key")
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing API key")
            
        # First validate against global API key
        logger.debug("=== API Key Validation Start ===")
        logger.debug(f"Full received API key header: {api_key}")
        logger.debug(f"Full configured API key: {settings.API_KEY}")
        
        # For user-specific endpoints, validate against stored API key
        if request.method == "POST":
            try:
                body = await request.json()
                logger.debug(f"Full request body: {body}")
                user_id = body.get("user_id")
                
                if user_id:
                    db = SqliteDB()
                    stored_key = None
                    
                    if "twitter" in request.url.path:
                        # Just check if the provided key matches either stored key
                        stored_key = db.get_user_api_key(user_id, "twitter-oauth1")  # We can just check one since they're the same
                        
                        if not stored_key or stored_key != api_key:
                            logger.debug("User-specific API key mismatch")
                            logger.debug(f"Keys don't match: '{api_key}' != '{stored_key}'")
                            raise HTTPException(status_code=401, detail="Invalid API key")
                    else:
                        # For other platforms, check normally
                        platform = request.url.path.split("/")[2]  # Get platform from URL
                        stored_key = db.get_user_api_key(user_id, platform)
                    
                    logger.debug(f"Full stored API key from DB: {stored_key}")
                    
                    if not stored_key or stored_key != api_key:
                        logger.debug("User-specific API key mismatch")
                        logger.debug(f"Keys don't match: '{api_key}' != '{stored_key}'")
                        raise HTTPException(status_code=401, detail="Invalid API key")
                        
            except json.JSONDecodeError:
                pass  # Not a JSON body, skip user-specific validation
                
        response = await call_next(request)
        return response
        
    except HTTPException as he:
        logger.error(f"HTTP error occurred: {he.detail}")
        return JSONResponse(
            status_code=he.status_code,
            content={"detail": he.detail}
        )
    except Exception as e:
        logger.error(f"Error in API key validation: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Add callback routes WITHOUT API key requirement
app.include_router(
    callback_router,
    prefix="/oauth",
    tags=["oauth-callbacks"],
)

# Add protected routes WITH API key requirement
app.include_router(
    oauth_router,
    prefix="/oauth",
    tags=["oauth"],
    dependencies=[Depends(get_api_key)],
)

@app.get("/")
async def root():
    """Root endpoint to verify service is running."""
    return {
        "message": "OAuth Service is running",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat(),
        "debug_mode": settings.DEBUG,
        "allowed_origins": settings.ALLOWED_ORIGINS.split(',')
    }

@app.get("/oauth/test")
async def test_oauth_service():
    """Test endpoint to verify OAuth service configuration."""
    try:
        return {
            "status": "ok",
            "message": "OAuth service is properly configured",
            "environment": settings.ENVIRONMENT,
            "platforms_configured": list(settings.oauth_credentials.keys()),
            "allowed_origins": settings.ALLOWED_ORIGINS.split(','),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error in test endpoint: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP error occurred: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled error occurred: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

# Run the application
if __name__ == "__main__":
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = settings.LOG_FORMAT
    
    if settings.ENVIRONMENT == "development":
        logger.info("Starting server in development mode")
        uvicorn.run(
            "oauth_service.main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=True,
            log_level=settings.LOG_LEVEL.lower(),
            log_config=log_config
        )
    else:
        logger.info(f"Starting server in {settings.ENVIRONMENT} mode")
        uvicorn.run(
            "oauth_service.main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=False,
            workers=settings.WORKERS,
            log_level=settings.LOG_LEVEL.lower(),
            log_config=log_config
        )