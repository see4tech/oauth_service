from typing import Dict, Optional, List
import tweepy
from requests_oauthlib import OAuth2Session
import aiohttp
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger

logger = get_logger(__name__)

class TwitterOAuth(OAuthBase):
    """Twitter OAuth implementation supporting both OAuth 1.0a and OAuth 2.0."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="twitter")
        
        # Decrypt client secret once
        decrypted_secret = self.crypto.decrypt(self._client_secret)
        
        # OAuth 1.0a setup for media uploads
        self.oauth1_handler = tweepy.OAuthHandler(
            self.client_id,
            decrypted_secret,
            callback_url
        )
        
        # OAuth 2.0 setup for API v2
        self.oauth2_client = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=callback_url,
            scope=['tweet.read', 'tweet.write', 'users.read'],
            code_challenge_method='S256'  # Enable PKCE by default
        )
        # Store decrypted secret for token exchange
        self._decrypted_secret = decrypted_secret
    
    async def get_authorization_url(self, state: Optional[str] = None) -> Dict[str, str]:
        """
        Get authorization URLs for both OAuth 1.0a and 2.0.
        
        Args:
            state: Optional state parameter for CSRF protection
            
        Returns:
            Dictionary containing both OAuth 1.0a and 2.0 authorization URLs
        """
        try:
            # Get OAuth 2.0 authorization URL with PKCE
            oauth2_auth_url, oauth2_state = self.oauth2_client.authorization_url(
                'https://twitter.com/i/oauth2/authorize',
                state=state,
                response_type='code',
                code_challenge_method='S256'
            )
            
            # Get OAuth 1.0a authorization URL
            oauth1_auth_url = self.oauth1_handler.get_authorization_url()
            
            logger.debug(f"Generated OAuth 2.0 URL: {oauth2_auth_url}")
            logger.debug(f"Generated OAuth 1.0a URL: {oauth1_auth_url}")
            
            return {
                'oauth1_url': oauth1_auth_url,
                'oauth2_url': oauth2_auth_url,
                'state': oauth2_state
            }
        except Exception as e:
            logger.error(f"Error getting authorization URLs: {str(e)}")
            raise
    
    async def get_access_token(self, 
                             oauth2_code: Optional[str] = None,
                             oauth1_verifier: Optional[str] = None) -> Dict:
        """
        Exchange authorization codes for access tokens.
        
        Args:
            oauth2_code: Authorization code for OAuth 2.0
            oauth1_verifier: Verifier for OAuth 1.0a
            
        Returns:
            Dictionary containing both OAuth 1.0a and 2.0 tokens
        """
        tokens = {}
        
        # Handle OAuth 2.0 token exchange
        if oauth2_code:
            try:
                logger.debug("Exchanging OAuth 2.0 code for tokens")
                token = self.oauth2_client.fetch_token(
                    'https://api.twitter.com/2/oauth2/token',
                    code=oauth2_code,
                    client_id=self.client_id,
                    client_secret=self._decrypted_secret,
                    include_client_id=True
                )
                logger.debug("Successfully obtained OAuth 2.0 tokens")
                tokens['oauth2'] = {
                    'access_token': token['access_token'],
                    'refresh_token': token.get('refresh_token'),
                    'expires_in': token.get('expires_in', 7200),
                    'expires_at': token.get('expires_at')
                }
            except Exception as e:
                logger.error(f"Error exchanging OAuth 2.0 code: {str(e)}")
                raise
        
        # Handle OAuth 1.0a token exchange
        if oauth1_verifier:
            try:
                logger.debug("Exchanging OAuth 1.0a verifier for tokens")
                self.oauth1_handler.get_access_token(oauth1_verifier)
                logger.debug("Successfully obtained OAuth 1.0a tokens")
                tokens['oauth1'] = {
                    'access_token': self.oauth1_handler.access_token,
                    'access_token_secret': self.oauth1_handler.access_token_secret
                }
            except Exception as e:
                logger.error(f"Error exchanging OAuth 1.0a verifier: {str(e)}")
                raise
        
        return tokens
    
    async def refresh_token(self, refresh_token: str) -> Dict:
        """
        Refresh OAuth 2.0 access token.
        
        Args:
            refresh_token: Refresh token from previous authorization
            
        Returns:
            Dictionary containing new access token data
        """
        token = self.oauth2_client.refresh_token(
            'https://api.twitter.com/2/oauth2/token',
            refresh_token=refresh_token,
            client_id=self.client_id,
            client_secret=self._decrypted_secret
        )
        
        return {
            'oauth2': {
                'access_token': token['access_token'],
                'refresh_token': token.get('refresh_token'),
                'expires_in': token.get('expires_in', 7200),
                'expires_at': token.get('expires_at')
            }
        }
    
    async def upload_media(self, token_data: Dict, media_content: bytes,
                          filename: str) -> Dict[str, str]:
        """
        Upload media using OAuth 1.0a.
        
        Args:
            token_data: Dictionary containing OAuth tokens
            media_content: Bytes of media content
            filename: Name of the media file
            
        Returns:
            Dictionary containing media ID
        """
        if 'oauth1' not in token_data:
            raise ValueError("OAuth 1.0a tokens required for media upload")
        
        auth = tweepy.OAuthHandler(
            self.client_id,
            self._decrypted_secret
        )
        auth.set_access_token(
            token_data['oauth1']['access_token'],
            token_data['oauth1']['access_token_secret']
        )
        
        api = tweepy.API(auth)
        media = api.media_upload(filename=filename, file=media_content)
        
        return {'media_id': str(media.media_id)}
    
    async def create_tweet(self, token_data: Dict, content: Dict) -> Dict:
        """
        Create a tweet using OAuth 2.0.
        
        Args:
            token_data: Dictionary containing OAuth tokens
            content: Tweet content including text and media IDs
            
        Returns:
            Dictionary containing tweet data
        """
        if 'oauth2' not in token_data:
            raise ValueError("OAuth 2.0 tokens required for creating tweets")
        
        client = tweepy.Client(
            bearer_token=None,
            consumer_key=self.client_id,
            consumer_secret=self._decrypted_secret,
            access_token=token_data['oauth2']['access_token']
        )
        
        # Handle media attachments
        media_ids = []
        if content.get('media_urls'):
            for media_url in content['media_urls']:
                media_result = await self.upload_media(
                    token_data,
                    await self._fetch_media(media_url),
                    f"media_{len(media_ids)}"
                )
                media_ids.append(media_result['media_id'])
        
        # Create tweet
        tweet = client.create_tweet(
            text=content['text'],
            media_ids=media_ids if media_ids else None
        )
        
        return {
            'tweet_id': tweet.data['id'],
            'text': tweet.data['text']
        }
    
    async def _fetch_media(self, url: str) -> bytes:
        """
        Fetch media content from URL.
        
        Args:
            url: URL of media content
            
        Returns:
            Bytes of media content
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                return await response.read()
