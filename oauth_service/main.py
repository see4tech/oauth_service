from fastapi import FastAPI, Security, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from .routes import oauth_router
from .config import get_settings
import uvicorn
import logging
from .utils.logger import get_logger

# Initialize settings and logger
settings = get_settings()
logger = get_logger(__name__)

# API Key security
API_KEY_NAME = "x-api-key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not settings.API_KEY:
        return None  # No API key required if not set
        
    if not api_key_header:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="No API key provided"
        )
    if api_key_header != settings.API_KEY:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    return api_key_header

app = FastAPI(
    title="OAuth Service",
    description="A comprehensive OAuth implementation supporting multiple platforms",
    version="1.0.0"
)

# Add origin logging middleware
@app.middleware("http")
async def log_origin(request: Request, call_next):
    # Log the origin URL
    origin = request.headers.get('origin')
    logger.info(f"Request Origin: {origin}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request Method: {request.method}")
    
    response = await call_next(request)
    return response

# Configure CORS with broader settings for your domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://33d10367-52d6-4ff5-99d8-1c6792f179e5.lovableproject.com",
        "http://localhost:3000",  # For local development
        "http://localhost:8000",  # For API server
        "https://dukat.see4.tech"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],  # Including x-api-key
    expose_headers=["*"],
    max_age=600,
)

# Include routes with API key dependency if configured
if settings.API_KEY:
    app.include_router(
        oauth_router,
        prefix="/oauth",
        dependencies=[Depends(get_api_key)],
        tags=["oauth"]
    )
else:
    app.include_router(
        oauth_router,
        prefix="/oauth",
        tags=["oauth"]
    )

# Add an explicit OPTIONS handler
@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str):
    return {"status": "ok"}

# Health check endpoint (no API key required)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "host": settings.SERVER_HOST,
        "port": settings.SERVER_PORT
    }

# Root endpoint (no API key required)
@app.get("/")
async def root():
    return {
        "message": "OAuth Service API",
        "documentation": "/docs",
        "redoc": "/redoc"
    }

if __name__ == "__main__":
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = settings.LOG_FORMAT
    
    print(f"Starting server on {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Log level: {settings.LOG_LEVEL}")
    
    if settings.ENVIRONMENT == "development":
        print("Warning: Running in development mode with reload enabled")
        if settings.API_KEY:
            print(f"API Key is set: {settings.API_KEY[:4]}...")
        else:
            print("No API Key set")
        uvicorn.run(
            "oauth_service.main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=True,
            log_level=settings.LOG_LEVEL.lower(),
            log_config=log_config
        )
    else:
        print(f"Running in production mode with {settings.WORKERS} workers")
        uvicorn.run(
            "oauth_service.main:app",
            host=settings.SERVER_HOST,
            port=settings.SERVER_PORT,
            reload=False,
            workers=settings.WORKERS,
            log_level=settings.LOG_LEVEL.lower(),
            log_config=log_config
        )