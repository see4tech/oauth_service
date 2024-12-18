from fastapi import FastAPI, Security, HTTPException, Depends, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from contextlib import asynccontextmanager
from .routes.oauth_routes import router as oauth_router
from .routes.oauth_callbacks import callback_router
from .config import get_settings
import uvicorn
import logging
from .utils.logger import get_logger
from datetime import datetime
from fastapi.responses import JSONResponse

# Initialize settings and logger
settings = get_settings()
logger = get_logger(__name__)

# API Key security
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not settings.API_KEY:
        return None
    if not api_key_header:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="No API key provided")
    if api_key_header != settings.API_KEY:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
    return api_key_header

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting OAuth Service in {settings.ENVIRONMENT} environment")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info(f"API documentation available at: {'/docs' if settings.ENVIRONMENT != 'production' else 'Disabled'}")
    
    yield  # Server is running
    
    # Shutdown
    logger.info("Shutting down OAuth Service")

# Initialize FastAPI app with lifespan
app = FastAPI(
    title="OAuth Service",
    description="A comprehensive OAuth implementation supporting multiple platforms",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan
)

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
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.utcnow().isoformat()
    }

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
        uvicorn.run(
            "oauth_service.main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=True,
            log_level=settings.LOG_LEVEL.lower(),
            log_config=log_config
        )
    else:
        uvicorn.run(
            "oauth_service.main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=False,
            workers=settings.WORKERS,
            log_level=settings.LOG_LEVEL.lower(),
            log_config=log_config
        )