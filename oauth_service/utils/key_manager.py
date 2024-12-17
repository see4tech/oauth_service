from pathlib import Path
from cryptography.fernet import Fernet
import os
import stat
from .logger import get_logger

logger = get_logger(__name__)

class KeyManager:
    """Manages encryption keys with secure storage."""
    
    def __init__(self):
        """Initialize key manager and set up secure key storage."""
        self.key_path = Path('data/.keys/fernet.key')
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key = self._load_or_create_key()
        
        # Set file permissions to be readable only by owner
        os.chmod(self.key_path, stat.S_IRUSR | stat.S_IWUSR)
    
    def _load_or_create_key(self) -> bytes:
        """
        Load existing key or create new one.
        
        Returns:
            Bytes containing the encryption key
        """
        try:
            if self.key_path.exists():
                with open(self.key_path, 'rb') as f:
                    key = f.read()
                    # Validate key format
                    if self._is_valid_key(key):
                        return key
                    logger.warning("Invalid key format found, generating new key")
            
            # Create new key if none exists or invalid
            key = Fernet.generate_key()
            with open(self.key_path, 'wb') as f:
                f.write(key)
            return key
            
        except Exception as e:
            logger.error(f"Error handling encryption key: {str(e)}")
            raise
    
    def _is_valid_key(self, key: bytes) -> bool:
        """
        Validate Fernet key format.
        
        Args:
            key: Bytes to validate as Fernet key
            
        Returns:
            Boolean indicating if key is valid
        """
        try:
            Fernet(key)
            return True
        except Exception:
            return False
    
    def get_fernet(self) -> Fernet:
        """
        Get Fernet instance with current key.
        
        Returns:
            Initialized Fernet instance
        """
        return Fernet(self.key)
    
    def rotate_key(self) -> None:
        """Generate new key and re-encrypt existing data."""
        # Note: Implementation would need to coordinate with TokenManager
        # to re-encrypt all stored tokens with new key
        raise NotImplementedError("Key rotation not yet implemented")
