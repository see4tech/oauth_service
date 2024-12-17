import pytest
from oauth_service.core import TokenManager, OAuthBase
from oauth_service.utils.crypto import FernetEncryption
import json

@pytest.mark.asyncio
async def test_token_storage_and_retrieval(token_manager, mock_tokens):
    """Test storing and retrieving tokens."""
    platform = 'test_platform'
    user_id = 'test_user'
    
    # Store tokens
    await token_manager.store_token(platform, user_id, mock_tokens)
    
    # Retrieve tokens
    retrieved_tokens = await token_manager.get_valid_token(platform, user_id)
    
    assert retrieved_tokens['oauth2']['access_token'] == mock_tokens['oauth2']['access_token']
    assert retrieved_tokens['oauth2']['refresh_token'] == mock_tokens['oauth2']['refresh_token']

@pytest.mark.asyncio
async def test_token_encryption(crypto):
    """Test token encryption and decryption."""
    test_data = "sensitive_data"
    
    # Encrypt data
    encrypted = crypto.encrypt(test_data)
    assert encrypted != test_data
    
    # Decrypt data
    decrypted = crypto.decrypt(encrypted)
    assert decrypted == test_data

@pytest.mark.asyncio
async def test_invalid_token_handling(token_manager):
    """Test handling of invalid or non-existent tokens."""
    result = await token_manager.get_valid_token('nonexistent', 'unknown_user')
    assert result is None
