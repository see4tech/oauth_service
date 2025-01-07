import secrets
from cryptography.fernet import Fernet
from typing import Optional, Dict
import os
import base64
import json
import time
from .logger import get_logger
from ..config import get_settings

logger = get_logger(__name__)

class FernetEncryption:
    """Handles encryption and decryption of sensitive data."""
    
    _instance = None
    
    def __new__(cls, key: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(key)
        return cls._instance

    def _initialize(self, key: Optional[str] = None):
        """Initialize with encryption key."""
        try:
            # Get key from parameter or environment
            key_str = key or os.getenv("ENCRYPTION_KEY")
            
            if not key_str:
                logger.error("No encryption key provided")
                raise ValueError("Encryption key is required")

            # Ensure key is properly formatted
            try:
                # Decode the base64 key
                key_bytes = base64.urlsafe_b64decode(key_str)
                
                # Verify key length
                if len(key_bytes) != 32:
                    raise ValueError(f"Invalid key length: {len(key_bytes)} bytes. Expected 32 bytes.")
                
                # Create Fernet instance
                self.cipher_suite = Fernet(key_str.encode() if isinstance(key_str, str) else key_str)
                logger.info("Fernet encryption initialized successfully")
                
            except Exception as e:
                logger.error(f"Invalid encryption key format: {str(e)}")
                raise ValueError("Encryption key must be 32 url-safe base64-encoded bytes")
                
        except Exception as e:
            logger.error(f"Encryption initialization error: {str(e)}")
            raise
    
    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        try:
            if not isinstance(data, str):
                raise ValueError(f"Data must be string, got {type(data)}")
            
            encrypted = self.cipher_suite.encrypt(data.encode())
            return encrypted.decode()
            
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt encrypted string."""
        try:
            if not isinstance(encrypted_data, str):
                raise ValueError(f"Encrypted data must be string, got {type(encrypted_data)}")
            
            decrypted = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            raise

class Crypto:
    def __init__(self):
        settings = get_settings()
        self.fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    
    def encrypt(self, data: str) -> str:
        """Encrypt data using Fernet."""
        return self.fernet.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data using Fernet."""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

def generate_api_key() -> str:
    """Generate a random API key."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')

def generate_oauth_state(user_id: str, frontend_callback_url: str, platform: str) -> str:
    """Generate and encrypt OAuth state parameter."""
    try:
        # Create state data
        state_data = {
            'user_id': user_id,
            'frontend_callback_url': frontend_callback_url,
            'platform': platform,
            'timestamp': int(time.time())  # Current Unix timestamp
        }
        
        # Convert to JSON and encode to bytes
        state_json = json.dumps(state_data)
        state_bytes = state_json.encode('utf-8')
        
        # Base64 encode for URL safety
        state = base64.urlsafe_b64encode(state_bytes).decode('utf-8')
        
        logger.debug(f"Generated OAuth state for user {user_id} and platform {platform}")
        logger.debug(f"State data: {state_data}")
        return state
        
    except Exception as e:
        logger.error(f"Error generating OAuth state: {str(e)}")
        raise

def verify_oauth_state(state: str) -> Dict:
    """Verify and decrypt OAuth state parameter."""
    try:
        # Decode base64
        state_bytes = base64.urlsafe_b64decode(state.encode('utf-8'))
        state_json = state_bytes.decode('utf-8')
        state_data = json.loads(state_json)
        
        # Verify required fields
        required_fields = ['user_id', 'frontend_callback_url', 'platform', 'timestamp']
        if not all(field in state_data for field in required_fields):
            logger.error("Invalid state data: missing required fields")
            return None
        
        # Verify timestamp (optional: add expiration check)
        # timestamp = int(state_data['timestamp'])
        # if time.time() - timestamp > 3600:  # 1 hour expiration
        #     logger.error("State expired")
        #     return None
        
        logger.debug(f"Verified OAuth state for user {state_data['user_id']}")
        return state_data
        
    except Exception as e:
        logger.error(f"Error verifying OAuth state: {str(e)}")
        return None