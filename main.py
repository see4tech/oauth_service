from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes import oauth_router
from dotenv import load_dotenv
import uvicorn
import os

# Load environment variables
load_dotenv()

app = FastAPI(
    title="OAuth Service",
    description="A comprehensive OAuth implementation supporting multiple platforms",
    version="1.0.0"
)

# Configure CORS
# In development, allow all origins
if os.getenv("ENVIRONMENT") == "development":
    origins = ["*"]
else:
    # In production, use configured origins or a secure default
    default_origins = [
        "http://localhost:3000",          # Local development
        "http://localhost:8000",          # Local API
        "https://your-domain.com",        # Your main domain
        "https://*.your-domain.com",      # Subdomains
    ]
    origins = os.getenv("ALLOWED_ORIGINS", ",".join(default_origins)).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.your-domain\.com",  # Allow all subdomains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Include routes
app.include_router(oauth_router, prefix="/oauth", tags=["oauth"])

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development")
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
    uvicorn.run(
        "oauth_service.main:app",
        host=os.getenv("SERVER_HOST", "0.0.0.0"),
        port=int(os.getenv("SERVER_PORT", 8000)),
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        workers=int(os.getenv("WORKERS", 1))
    )
