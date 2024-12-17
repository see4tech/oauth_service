from cryptography.fernet import Fernet
from typing import Optional
import os
import base64
from .logger import get_logger

logger = get_logger(__name__)

class FernetEncryption:
    """Handles encryption and decryption of sensitive data."""
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize Fernet encryption with provided or environment key.
        
        Args:
            key: Optional encryption key. If not provided, uses ENCRYPTION_KEY from environment
        """
        self.key = key or os.getenv("ENCRYPTION_KEY") or Fernet.generate_key()
        if isinstance(self.key, str):
            # Handle base64 encoded string from environment
            try:
                base64.b64decode(self.key)
            except Exception:
                logger.warning("Invalid key format, generating new key")
                self.key = Fernet.generate_key()
        self.cipher_suite = Fernet(self.key)
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.
        
        Args:
            data: String to encrypt
            
        Returns:
            Encrypted string in base64 format
        """
        try:
            return self.cipher_suite.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted string.
        
        Args:
            encrypted_data: Encrypted string in base64 format
            
        Returns:
            Decrypted string
        """
        try:
            return self.cipher_suite.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            raise
