import pytest
from oauth_service.platforms import TwitterOAuth, LinkedInOAuth
import os

@pytest.mark.asyncio
async def test_twitter_oauth_flow():
    """Test Twitter OAuth flow."""
    oauth = TwitterOAuth(
        client_id="test_id",
        client_secret="test_secret",
        callback_url="http://localhost/callback"
    )
    
    # Test authorization URL generation
    auth_urls = await oauth.get_authorization_url()
    assert 'oauth1_url' in auth_urls
    assert 'oauth2_url' in auth_urls
    assert auth_urls['oauth2_url'].startswith('https://twitter.com/')

@pytest.mark.asyncio
async def test_linkedin_oauth_flow():
    """Test LinkedIn OAuth flow."""
    oauth = LinkedInOAuth(
        client_id="test_id",
        client_secret="test_secret",
        callback_url="http://localhost/callback"
    )
    
    # Test authorization URL generation
    auth_url = await oauth.get_authorization_url()
    assert auth_url.startswith('https://www.linkedin.com/oauth/v2/authorization')
    assert 'client_id=test_id' in auth_url

@pytest.mark.asyncio
async def test_token_refresh():
    """Test token refresh functionality."""
    oauth = LinkedInOAuth(
        client_id="test_id",
        client_secret="test_secret",
        callback_url="http://localhost/callback"
    )
    
    with pytest.raises(Exception):
        # Should raise exception with invalid refresh token
        await oauth.refresh_token("invalid_token")
