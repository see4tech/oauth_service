from fastapi import FastAPI, Security, HTTPException, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from .routes import oauth_router
from .config import get_settings
import uvicorn
import logging
import re
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

# Comprehensive CORS Middleware with Extensive Debugging
@app.middleware("http")
async def debug_cors_middleware(request: Request, call_next):
    # Log all incoming request details
    logger.info(f"Incoming Request:")
    logger.info(f"Method: {request.method}")
    logger.info(f"URL: {request.url}")
    
    # Log all headers
    headers = dict(request.headers)
    for key, value in headers.items():
        logger.info(f"Header - {key}: {value}")
    
    response = await call_next(request)
    
    # Log response headers
    logger.info(f"Response Headers:")
    for key, value in response.headers.items():
        logger.info(f"Header - {key}: {value}")
    
    return response

# CORS Configuration with Maximum Flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Most permissive for debugging
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400  # 24 hours
)

# CORS Debugging Endpoint
@app.get("/cors-debug")
async def cors_debug(request: Request):
    # Collect all headers for debugging
    headers = dict(request.headers)
    return {
        "headers": headers,
        "origin": request.headers.get('origin', 'No origin header'),
        "access_control_request_method": request.headers.get('access-control-request-method', 'No access control method'),
        "host": request.headers.get('host', 'No host header')
    }

# Explicit OPTIONS Handler with Detailed Logging
@app.options("/{rest_of_path:path}")
async def options_handler(rest_of_path: str, request: Request):
    # Collect headers
    headers = dict(request.headers)
    
    # Log OPTIONS request details
    logger.info(f"OPTIONS Request - Path: {rest_of_path}")
    for key, value in headers.items():
        logger.info(f"OPTIONS Header - {key}: {value}")
    
    # Create response with comprehensive CORS headers
    return Response(
        content="OK",
        headers={
            "Access-Control-Allow-Origin": request.headers.get('origin', '*'),
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, PUT, DELETE",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "86400",
            "Access-Control-Allow-Credentials": "true"
        }
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