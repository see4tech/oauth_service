import pytest
import os
from pathlib import Path
from cryptography.fernet import Fernet
from oauth_service.core import TokenManager
from oauth_service.utils.crypto import FernetEncryption
from oauth_service.utils.key_manager import KeyManager

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment variables and directories."""
    os.environ['ENCRYPTION_KEY'] = Fernet.generate_key().decode()
    os.environ['ENVIRONMENT'] = 'test'
    
    # Create test directories
    test_data_dir = Path('test_data')
    test_data_dir.mkdir(exist_ok=True)
    (test_data_dir / '.keys').mkdir(exist_ok=True)
    
    yield
    
    # Cleanup
    import shutil
    shutil.rmtree(test_data_dir)

@pytest.fixture
def token_manager():
    """Provide test TokenManager instance."""
    return TokenManager()

@pytest.fixture
def crypto():
    """Provide test FernetEncryption instance."""
    return FernetEncryption()

@pytest.fixture
def key_manager():
    """Provide test KeyManager instance."""
    return KeyManager()

@pytest.fixture
def mock_tokens():
    """Provide mock OAuth tokens."""
    return {
        'oauth2': {
            'access_token': 'test_access_token',
            'refresh_token': 'test_refresh_token',
            'expires_in': 3600,
            'token_type': 'bearer'
        },
        'oauth1': {
            'access_token': 'test_oauth1_token',
            'access_token_secret': 'test_oauth1_secret'
        }
    }
