from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from oauth_service.routes import oauth_router
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

# Include routes
app.include_router(oauth_router, prefix="/oauth", tags=["oauth"])

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": ENVIRONMENT,
        "host": SERVER_HOST,
        "port": SERVER_PORT
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
    print(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    print(f"Environment: {ENVIRONMENT}")
    print(f"Log level: {LOG_LEVEL}")
    
    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=ENVIRONMENT == "development",
        log_level=LOG_LEVEL,
        workers=WORKERS
    )