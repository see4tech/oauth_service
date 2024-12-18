from cryptography.fernet import Fernet
from typing import Optional
import os
import base64
from .logger import get_logger

logger = get_logger(__name__)

class FernetEncryption:
    """Handles encryption and decryption of sensitive data."""
    
    _instance = None
    
    def __new__(cls, key: Optional[str] = None):
        """Ensure single instance with same key across the application."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_key(key)
        return cls._instance
    
    def _init_key(self, key: Optional[str] = None):
        """Initialize the encryption key."""
        try:
            # Try to get key from parameter or environment
            self.key = key or os.getenv("ENCRYPTION_KEY")
            
            if self.key:
                # If key is provided as string, ensure it's valid base64
                if isinstance(self.key, str):
                    try:
                        # Try to decode and validate the key
                        key_bytes = base64.b64decode(self.key)
                        if len(key_bytes) != 32:
                            raise ValueError("Invalid key length")
                        self.key = key_bytes
                    except Exception as e:
                        logger.error(f"Invalid encryption key format: {str(e)}")
                        self.key = Fernet.generate_key()
            else:
                # Generate new key if none provided
                logger.warning("No encryption key provided, generating new one")
                self.key = Fernet.generate_key()
            
            # Initialize Fernet cipher suite
            self.cipher_suite = Fernet(self.key if isinstance(self.key, bytes) else self.key.encode())
            logger.debug(f"Initialized Fernet encryption with key: {self.key[:10]}...")
            
        except Exception as e:
            logger.error(f"Error initializing encryption: {str(e)}")
            raise
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.
        
        Args:
            data: String to encrypt
            
        Returns:
            Encrypted string in base64 format
        """
        try:
            if not isinstance(data, str):
                raise ValueError(f"Data must be string, got {type(data)}")
                
            encrypted = self.cipher_suite.encrypt(data.encode())
            return encrypted.decode()
            
        except Exception as e:
            logger.error(f"Encryption error: {str(e)}")
            logger.error(f"Failed to encrypt data: {data[:30]}...")
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
            if not isinstance(encrypted_data, str):
                raise ValueError(f"Encrypted data must be string, got {type(encrypted_data)}")
                
            decrypted = self.cipher_suite.decrypt(encrypted_data.encode())
            return decrypted.decode()
            
        except Exception as e:
            logger.error(f"Decryption error: {str(e)}")
            logger.error(f"Failed to decrypt data: {encrypted_data[:30]}...")
            raise