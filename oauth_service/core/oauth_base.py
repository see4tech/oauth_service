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
        """Generate secure state with user_id and frontend callback URL."""
        state_data = {
            'user_id': user_id,
            'frontend_callback_url': frontend_callback_url,
            'timestamp': datetime.utcnow().timestamp()
        }
        return self.crypto.encrypt(json.dumps(state_data))
    
    def verify_state(self, state: str) -> Optional[Dict]:
        """Verify state and return user_id and frontend_callback_url."""
        try:
            decrypted = self.crypto.decrypt(state)
            state_data = json.loads(decrypted)
            timestamp = datetime.fromtimestamp(state_data['timestamp'])
            
            # Verify state is not older than 1 hour
            if (datetime.utcnow() - timestamp).total_seconds() > 3600:
                return None
                
            return {
                'user_id': state_data['user_id'],
                'frontend_callback_url': state_data['frontend_callback_url']
            }
        except Exception as e:
            logger.error(f"Error verifying state: {str(e)}")
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
