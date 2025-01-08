from cryptography.fernet import Fernet
from ..config import get_settings
import base64
import hashlib
from typing import Optional

settings = get_settings()

def get_encryption_key():
    """Generate a consistent encryption key based on the API_KEY."""
    if not settings.API_KEY:
        raise ValueError("API_KEY must be set in environment variables")
    # Use API_KEY to generate a consistent 32-byte key
    return base64.urlsafe_b64encode(hashlib.sha256(settings.API_KEY.encode()).digest())

def encrypt_api_key(api_key: str) -> str:
    """Encrypt the API key before storing."""
    if not api_key:
        return None
    
    try:
        f = Fernet(get_encryption_key())
        encrypted = f.encrypt(api_key.encode())
        return base64.urlsafe_b64encode(encrypted).decode()
    except Exception as e:
        logger.error(f"Error encrypting API key: {str(e)}")
        return None

def decrypt_api_key(encrypted_key: str) -> Optional[str]:
    """Decrypt the stored API key."""
    if not encrypted_key:
        return None
    
    try:
        f = Fernet(get_encryption_key())
        decoded = base64.urlsafe_b64decode(encrypted_key.encode())
        decrypted = f.decrypt(decoded)
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Error decrypting API key: {str(e)}")
        return None 