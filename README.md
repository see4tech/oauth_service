## Setup and Installation

### 1. Directory Structure
Ensure your project has the following structure:
```
oauth_service/
├── setup.py
├── requirements.txt
├── init_db.py
├── README.md
├── oauth_service/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   └── ...
│   ├── platforms/
│   │   ├── __init__.py
│   │   ├── twitter.py
│   │   └── ...
│   └── ...
└── data/           (will be created during initialization)
    └── .keys/
```

### 2. Environment Setup
```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Unix or MacOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install package in development mode
pip install -e .
```

### 3. Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your credentials
# Required variables:
# - TWITTER_CLIENT_ID
# - TWITTER_CLIENT_SECRET
# - LINKEDIN_CLIENT_ID
# - LINKEDIN_CLIENT_SECRET
# etc...
```

### 4. Initialize Database
```bash
# Run the initialization script
python init_db.py

# This will:
# - Create the data directory
# - Create the .keys directory with proper permissions
# - Initialize the SQLite database
```

### 5. Start the Application
```bash
# Method 1: Using python directly
python oauth_service/main.py

# Method 2: Using uvicorn
uvicorn oauth_service.main:app --host 0.0.0.0 --port 8000 --reload

# The API will be available at:
# - API documentation: http://localhost:8000/docs
# - Alternative docs: http://localhost:8000/redoc
# - Health check: http://localhost:8000/health
```

### Development vs Production

#### Development
```bash
# In .env:
ENVIRONMENT=development
DEBUG=True

# Start with reload:
uvicorn oauth_service.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Production
```bash
# In .env:
ENVIRONMENT=production
DEBUG=False

# Start with gunicorn (recommended for production):
gunicorn oauth_service.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Troubleshooting

#### Common Issues

1. Module Not Found Errors
```bash
# Ensure you're in the project root and run:
pip install -e .
```

2. Permission Issues
```bash
# On Unix systems, ensure proper permissions:
chmod 700 data/.keys
```

3. Database Initialization Fails
```bash
# Check directory permissions
# Ensure SQLite is available
# Verify database path in .env
```

4. OAuth Errors
```bash
# Verify credentials in .env
# Check callback URLs match your OAuth app settings
# Ensure proper scopes are configured
```

### Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OAuth 2.0 Specification](https://oauth.net/2/)
- Platform-specific docs:
  - [Twitter OAuth Documentation](https://developer.twitter.com/en/docs/authentication/oauth-2-0)
  - [LinkedIn OAuth Documentation](https://docs.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow)
  - [Facebook OAuth Documentation](https://developers.facebook.com/docs/facebook-login/guides/access-tokens)
  - [Instagram OAuth Documentation](https://developers.facebook.com/docs/instagram-basic-display-api/overview)
