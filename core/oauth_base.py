from abc import ABC, abstractmethod
from typing import Dict, Optional
from datetime import datetime
import secrets
from ..utils.crypto import FernetEncryption
from ..utils.logger import get_logger

logger = get_logger(__name__)

class OAuthBase(ABC):
    """Base class for OAuth implementations."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        """
        Initialize OAuth base class.
        
        Args:
            client_id: OAuth client ID
            client_secret: OAuth client secret
            callback_url: OAuth callback URL
        """
        self.client_id = client_id
        self.callback_url = callback_url
        self.crypto = FernetEncryption()
        self._client_secret = self.crypto.encrypt(client_secret)
        self.platform_name = self.__class__.__name__.lower()
    
    @abstractmethod
    async def get_authorization_url(self, state: Optional[str] = None) -> str:
        """
        Get the authorization URL for OAuth flow.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL string
        """
        pass
    
    @abstractmethod
    async def get_access_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.
        
        Args:
            code: Authorization code from callback
            
        Returns:
            Dictionary containing access token and related data
        """
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> Dict:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: Refresh token from previous authorization
            
        Returns:
            Dictionary containing new access token and related data
        """
        pass
    
    def generate_state(self, user_id: str) -> str:
        """
        Generate secure state parameter for CSRF protection.
        
        Args:
            user_id: User identifier to include in state
            
        Returns:
            Encrypted state string
        """
        state_data = {
            'user_id': user_id,
            'timestamp': datetime.utcnow().timestamp(),
            'random': secrets.token_urlsafe(16)
        }
        return self.crypto.encrypt(str(state_data))
    
    def verify_state(self, state: str) -> Optional[str]:
        """
        Verify and extract user_id from state parameter.
        
        Args:
            state: State parameter from callback
            
        Returns:
            User ID if state is valid, None otherwise
        """
        try:
            state_data = eval(self.crypto.decrypt(state))
            timestamp = datetime.fromtimestamp(state_data['timestamp'])
            
            # Verify state is not older than 1 hour
            if (datetime.utcnow() - timestamp).total_seconds() > 3600:
                return None
                
            return state_data['user_id']
        except Exception as e:
            logger.error(f"Error verifying state: {str(e)}")
            return None
