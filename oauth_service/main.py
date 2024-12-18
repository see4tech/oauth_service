from fastapi import FastAPI, Security, HTTPException, Depends, APIRouter, Request
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
        return None
    if not api_key_header:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="No API key provided")
    if api_key_header != settings.API_KEY:
        raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Invalid API key")
    return api_key_header

app = FastAPI(
    title="OAuth Service",
    description="A comprehensive OAuth implementation supporting multiple platforms",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://33d10367-52d6-4ff5-99d8-1c6792f179e5.lovableproject.com",
        "http://localhost:3000",
        "http://localhost:8000",
        "https://dukat.see4.tech"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Include routes with API key requirement for non-callback endpoints
app.include_router(
    oauth_router,
    prefix="/oauth",
    tags=["oauth"],
    dependencies=[Depends(get_api_key)],
    include_in_schema=True
)

# Add callback routes without API key requirement
callback_router = APIRouter()

@callback_router.get("/{platform}/callback")
async def oauth_callback(request: Request, platform: str):
    return await oauth_router.url_path_for("oauth_callback")(request=request, platform=platform)

app.include_router(callback_router, prefix="/oauth")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "host": settings.SERVER_HOST,
        "port": settings.SERVER_PORT
    }

# Root endpoint
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
