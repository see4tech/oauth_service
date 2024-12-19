from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from datetime import datetime
import json
import base64
from ..utils.crypto import FernetEncryption
from ..utils.logger import get_logger

logger = get_logger(__name__)

class OAuthBase(ABC):
    """Base class for OAuth implementations."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        self.client_id = client_id
        self.callback_url = callback_url
        self.crypto = FernetEncryption()
        self._client_secret = self.crypto.encrypt(client_secret)
        self.platform_name = self.__class__.__name__.lower()

    def generate_state(self, user_id: str, frontend_callback_url: str) -> str:
        """
        Generate secure state with user_id and frontend callback URL.
        
        Args:
            user_id: User identifier
            frontend_callback_url: URL to redirect after OAuth
            
        Returns:
            str: Encrypted state string
        """
        try:
            state_data = {
                'user_id': user_id,
                'frontend_callback_url': frontend_callback_url,
                'timestamp': datetime.utcnow().timestamp(),
                'platform': self.platform_name  # Add platform to state
            }
            
            # Log state data for debugging
            logger.debug(f"Generating state for platform {self.platform_name}")
            logger.debug(f"State data before encryption: {state_data}")
            
            # Convert to JSON and encrypt
            state_json = json.dumps(state_data)
            encrypted_state = self.crypto.encrypt(state_json)
            
            logger.debug(f"Generated encrypted state: {encrypted_state[:30]}...")
            return encrypted_state
            
        except Exception as e:
            logger.error(f"Error generating state: {str(e)}")
            raise
    
    def verify_state(self, state: str) -> Optional[Dict]:
        """
        Verify state and return user_id and frontend_callback_url.
        
        Args:
            state: Encrypted state string from OAuth callback
            
        Returns:
            Optional[Dict]: Decrypted state data or None if invalid
        """
        try:
            logger.debug(f"Verifying state for platform {self.platform_name}")
            logger.debug(f"Received state: {state[:30]}...")
            
            # Decrypt the state
            decrypted = self.crypto.decrypt(state)
            logger.debug(f"Decrypted state: {decrypted}")
            
            # Parse JSON
            state_data = json.loads(decrypted)
            
            # Verify timestamp
            timestamp = datetime.fromtimestamp(state_data['timestamp'])
            age = (datetime.utcnow() - timestamp).total_seconds()
            
            logger.debug(f"State age: {age} seconds")
            
            # Verify not expired (1 hour)
            if age > 3600:
                logger.warning(f"State expired. Age: {age} seconds")
                return None
            
            # Get platform from state
            state_platform = state_data.get('platform', '')
            
            # Verify platform matches (support both with and without 'oauth' suffix)
            if state_platform != self.platform_name and state_platform != self.platform_name.replace('oauth', ''):
                logger.warning(f"Platform mismatch. Expected: {self.platform_name}, Got: {state_platform}")
                return None
                
            return {
                'user_id': state_data['user_id'],
                'frontend_callback_url': state_data['frontend_callback_url']
            }
            
        except Exception as e:
            logger.error(f"Error verifying state: {str(e)}")
            logger.error(f"State verification failed for platform {self.platform_name}")
            return None

    @abstractmethod
    async def get_authorization_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None) -> str:
        """Get the authorization URL for OAuth flow."""
        pass

    @abstractmethod
    async def get_access_token(self, code: str) -> Dict:
        """Exchange authorization code for access token."""
        pass

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict:
        """Refresh an expired access token."""
        pass