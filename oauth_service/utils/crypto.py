import secrets
from cryptography.fernet import Fernet
from typing import Optional
import os
import base64
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
    """Generate a secure API key."""
    return f"user_{secrets.token_urlsafe(32)}"