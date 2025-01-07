import secrets
from cryptography.fernet import Fernet
from ..config import get_settings

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