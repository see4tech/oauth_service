# OAuth Service

A comprehensive OAuth implementation supporting multiple social media platforms with secure token management.

## Features
- Supports OAuth 1.0a and OAuth 2.0
- Platform implementations for Twitter, LinkedIn, Facebook, and Instagram
- Secure token storage using SQLite with Fernet encryption
- Protected key management
- Rate limiting and comprehensive logging
- Async support throughout

## Requirements
- Python 3.12.3 or higher
- Docker and Docker Compose (for containerized deployment)
- Redis (optional, for enhanced caching)

## Installation

### Local Development
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and update with your credentials
cp .env.example .env

# Initialize database and key storage
mkdir -p data/.keys
chmod 700 data/.keys  # On Unix systems
python -m oauth_service.core.db
```

### Docker Deployment
```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Configuration

### Environment Variables
Configure the service by setting these variables in your `.env` file:

```bash
# Server Configuration
SERVER_HOST=0.0.0.0
SERVER_PORT=8000
DEBUG=False
ENVIRONMENT=production  # production, development, staging

# Security
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-fernet-encryption-key-here
JWT_SECRET=your-jwt-secret-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Database
DATABASE_PATH=data/oauth.db

# Platform Credentials

# Twitter
TWITTER_CLIENT_ID=your-twitter-client-id
TWITTER_CLIENT_SECRET=your-twitter-client-secret
TWITTER_CALLBACK_URL=http://localhost:8000/oauth/twitter/callback

# LinkedIn
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
LINKEDIN_CALLBACK_URL=http://localhost:8000/oauth/linkedin/callback

# Instagram
INSTAGRAM_CLIENT_ID=your-instagram-client-id
INSTAGRAM_CLIENT_SECRET=your-instagram-client-secret
INSTAGRAM_CALLBACK_URL=http://localhost:8000/oauth/instagram/callback

# Facebook
FACEBOOK_CLIENT_ID=your-facebook-client-id
FACEBOOK_CLIENT_SECRET=your-facebook-client-secret
FACEBOOK_CALLBACK_URL=http://localhost:8000/oauth/facebook/callback

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=3600

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=%(asctime)s - %(name)s - %(levelname)s - %(message)s
LOG_FILE=oauth_service.log
```

### Directory Structure
```
oauth_service/
├── data/              # Data storage
│   ├── oauth.db       # SQLite database
│   └── .keys/        # Protected key storage
├── logs/             # Log files
├── oauth_service/    # Source code
└── tests/           # Test files
```

### Nginx Configuration
The service includes an Nginx configuration for production deployment:

1. Copy the Nginx configuration:
```bash
sudo cp nginx/conf.d/oauth_service.conf /etc/nginx/conf.d/
```

2. Update SSL certificates:
```bash
# Generate certificates
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/your-domain.key \
    -out /etc/nginx/ssl/your-domain.crt
```

3. Update the domain name in `oauth_service.conf`

### Security Configuration

1. Key Management:
```bash
# Set proper permissions
chmod 700 data/.keys
chmod 600 data/.keys/fernet.key
```

2. Database Security:
```bash
# Set proper permissions
chmod 600 data/oauth.db
```

3. Rate Limiting:
Configure in Nginx config or environment variables:
```nginx
# In nginx/conf.d/oauth_service.conf
limit_req_zone $binary_remote_addr zone=oauth_limit:10m rate=10r/s;
```

## API Documentation

The API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Health Checks

Monitor service health at:
```
http://localhost:8000/health
```

Response format:
```json
{
    "status": "healthy",
    "timestamp": "2024-03-17T12:00:00Z",
    "services": {
        "database": "up",
        "cache": "up"
    }
}
```

## Docker Compose Services

The `docker-compose.yml` includes:
- OAuth Service (`oauth_service`)
- Redis Cache (`redis`)
- Nginx Proxy (`nginx`)

Start specific services:
```bash
docker-compose up -d oauth_service
docker-compose up -d redis
```

## Testing

Run the test suite:
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=oauth_service

# Run specific test file
pytest tests/test_core.py
```

## Example Usage

### Twitter OAuth Flow
```python
from oauth_service import TwitterOAuth
from oauth_service.core import TokenManager

# Initialize OAuth handler
oauth = TwitterOAuth(
    client_id="your_client_id",
    client_secret="your_client_secret",
    callback_url="your_callback_url"
)

# Get authorization URL
auth_urls = await oauth.get_authorization_url()

# Handle callback and store tokens
tokens = await oauth.get_access_token(code="callback_code")
await token_manager.store_token("twitter", "user_id", tokens)
```

## Troubleshooting

### Common Issues

1. Database Access:
```bash
# Check permissions
ls -l data/oauth.db
# Should show: -rw------- 1 appuser appuser ...
```

2. Key Storage:
```bash
# Verify key directory permissions
ls -la data/.keys
# Should show: drwx------ 2 appuser appuser ...
```

3. Logs:
```bash
# View service logs
tail -f logs/oauth_service.log

# View Nginx logs
tail -f nginx/logs/access.log
tail -f nginx/logs/error.log
```

## License
MIT License

## Contributing
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
