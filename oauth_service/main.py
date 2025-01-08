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
    
    try:
        # Start token refresh service in the background
        asyncio.create_task(start_refresh_service())
        logger.info("Token refresh service started")
    except Exception as e:
        logger.error(f"Error starting token refresh service: {str(e)}")
    
    yield
    
    # Shutdown
    try:
        await stop_refresh_service()
        logger.info("Token refresh service stopped")
    except Exception as e:
        logger.error(f"Error stopping token refresh service: {str(e)}")
    
    logger.info("Shutting down OAuth Service")

async def get_api_key(api_key_header: str = Security(api_key_header), request: Request = None):
    """Validate API key from request header."""
    logger.debug("=== API Key Validation Start ===")
    logger.debug(f"Received API key header: {api_key_header[:4]}...{api_key_header[-4:] if api_key_header else None}")
    logger.debug(f"Configured API key: {settings.API_KEY[:4]}...{settings.API_KEY[-4:] if settings.API_KEY else None}")
    
    # Direct comparison with global API key
    if api_key_header == settings.API_KEY:
        logger.debug("Global API key validation successful")
        return api_key_header

    try:
        if request and request.method == "POST":
            try:
                body = await request.json()
                user_id = body.get("user_id")
                path_parts = request.url.path.split("/")
                platform = path_parts[2] if len(path_parts) > 2 else None
                
                if user_id and platform:
                    db = SqliteDB()
                    stored_api_key = db.get_user_api_key(user_id, platform)
                    
                    # Direct comparison with stored key
                    if stored_api_key and stored_api_key == api_key_header:
                        logger.debug("User-specific API key validation successful")
                        return api_key_header
                    
                    logger.debug("User-specific API key mismatch")
            except Exception as e:
                logger.error(f"Error processing request: {str(e)}")
                logger.error(f"Request path: {request.url.path}")
                logger.error(f"Request method: {request.method}")
    except Exception as e:
        logger.error(f"Error during API key validation: {str(e)}")
    
    raise HTTPException(
        status_code=HTTP_403_FORBIDDEN,
        detail="Invalid API key"
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