from fastapi import FastAPI, Security, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from .routes import oauth_router
from dotenv import load_dotenv
import uvicorn
import os

# Load environment variables
load_dotenv()

# Get server configuration from environment
SERVER_HOST = os.getenv("SERVER_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("SERVER_PORT", "8000"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "info").lower()
WORKERS = int(os.getenv("WORKERS", "1"))
API_KEY = os.getenv("API_KEY")

if not API_KEY and ENVIRONMENT == "production":
    raise ValueError("API_KEY must be set in production environment")

# API Key security
API_KEY_NAME = "x-api-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not api_key_header:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="No API key provided"
        )
    if api_key_header != API_KEY:
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

# Configure CORS
if ENVIRONMENT == "development":
    origins = ["*"]
else:
    origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
    if not origins:
        raise ValueError("ALLOWED_ORIGINS must be set in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,
)

# Include routes with API key dependency
app.include_router(
    oauth_router,
    dependencies=[Depends(get_api_key)],
    tags=["oauth"]
)

# Health check endpoint (no API key required)
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "host": SERVER_HOST,
        "port": SERVER_PORT
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
    print(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Log level: {LOG_LEVEL}")
    
    if ENVIRONMENT == "development":
        print("Warning: Running in development mode")
        if API_KEY:
            print(f"API Key is set: {API_KEY[:4]}...")
        else:
            print("No API Key set")
    
    uvicorn.run(
        "oauth_service.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=ENVIRONMENT == "development",
        log_level=LOG_LEVEL,
        workers=WORKERS
    )