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
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str, consumer_key: str = None, consumer_secret: str = None):
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="twitter")
        
        # Store OAuth 1.0a credentials separately
        self._consumer_key = consumer_key or client_id
        self._consumer_secret = consumer_secret or client_secret
        
        # Decrypt OAuth 2.0 client secret
        self._decrypted_client_secret = self.crypto.decrypt(self._client_secret)
        
        # For OAuth 1.0a, use raw secrets as they come from settings
        self._decrypted_consumer_secret = self._consumer_secret
        
        # OAuth 1.0a setup
        self.oauth1_handler = tweepy.OAuthHandler(
            self._consumer_key,
            self._decrypted_consumer_secret,
            callback_url
        )
        
        # OAuth 2.0 setup - with minimum required scopes
        self.oauth2_client = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=callback_url,
            scope=['tweet.read', 'tweet.write', 'users.read']
        )
    
    async def get_authorization_url(self, state: Optional[str] = None) -> Dict[str, str]:
        """Get authorization URLs for both OAuth 1.0a and 2.0."""
        result = {}
        
        # OAuth 2.0 first - this should always work as it doesn't require authentication
        try:
            logger.debug("Starting OAuth 2.0 authorization URL generation")
            
            # Generate PKCE challenge
            from base64 import urlsafe_b64encode
            import hashlib
            import secrets
            
            # Generate code verifier
            code_verifier = secrets.token_urlsafe(32)
            
            # Generate code challenge
            code_challenge_bytes = hashlib.sha256(code_verifier.encode('utf-8')).digest()
            code_challenge = urlsafe_b64encode(code_challenge_bytes).decode('utf-8').rstrip('=')
            
            # Add PKCE and specific parameters
            oauth2_auth_url, oauth2_state = self.oauth2_client.authorization_url(
                'https://twitter.com/i/oauth2/authorize',
                state=state,
                code_challenge=code_challenge,
                code_challenge_method='S256'
            )
            logger.debug(f"Generated OAuth 2.0 URL: {oauth2_auth_url}")
            result['oauth2_url'] = oauth2_auth_url
            result['state'] = oauth2_state
            result['code_verifier'] = code_verifier  # Include code verifier in result
            
            # Log URL components for debugging
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(oauth2_auth_url)
            params = parse_qs(parsed.query)
            logger.debug("OAuth 2.0 URL components:")
            logger.debug(f"- redirect_uri: {params.get('redirect_uri', [''])[0]}")
            logger.debug(f"- scope: {params.get('scope', [''])[0]}")
            logger.debug(f"- response_type: {params.get('response_type', [''])[0]}")
            logger.debug(f"- code_challenge_method: {params.get('code_challenge_method', [''])[0]}")
            logger.debug(f"- code_challenge: {params.get('code_challenge', [''])[0]}")
            
        except Exception as e:
            logger.error(f"Error generating OAuth 2.0 URL: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
        
        # OAuth 1.0a - handle separately as it requires request token
        try:
            logger.debug("Starting OAuth 1.0a authorization URL generation")
            oauth1_auth_url = self.oauth1_handler.get_authorization_url()
            logger.debug(f"Generated OAuth 1.0a URL: {oauth1_auth_url}")
            result['oauth1_url'] = oauth1_auth_url
        except Exception as e:
            logger.error(f"Error generating OAuth 1.0a URL: {str(e)}")
            result['oauth1_error'] = str(e)
        
        return result
    
    async def get_access_token(self, 
                             oauth2_code: Optional[str] = None,
                             oauth1_verifier: Optional[str] = None,
                             code_verifier: Optional[str] = None) -> Dict:
        """Exchange authorization codes for access tokens."""
        tokens = {}
        
        if oauth2_code:
            try:
                # Include code verifier for PKCE
                token = self.oauth2_client.fetch_token(
                    'https://api.twitter.com/2/oauth2/token',
                    code=oauth2_code,
                    client_secret=self._decrypted_client_secret,
                    code_verifier=code_verifier
                )
                tokens['oauth2'] = {
                    'access_token': token['access_token'],
                    'refresh_token': token.get('refresh_token'),
                    'expires_in': token.get('expires_in', 7200),
                    'expires_at': token.get('expires_at')
                }
            except Exception as e:
                logger.error(f"Error exchanging OAuth 2.0 code: {str(e)}")
                raise
        
        if oauth1_verifier:
            try:
                self.oauth1_handler.get_access_token(oauth1_verifier)
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
            client_secret=self._decrypted_client_secret
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
            self._consumer_key,
            self._decrypted_consumer_secret
        )
        auth.set_access_token(
            token_data['oauth1']['access_token'],
            token_data['oauth1']['access_token_secret']
        )
        
        api = tweepy.API(auth)
        media = api.media_upload(filename=filename, file=media_content)
        
        return {'media_id': str(media.media_id)}
    
    async def upload_media_v1(self, token_data: Dict, image_url: str) -> str:
        """
        Upload media using Twitter API v1.1.
        
        Args:
            token_data: Dictionary containing OAuth tokens
            image_url: URL of the image to upload
            
        Returns:
            Media ID string
        """
        try:
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if not response.ok:
                        raise ValueError(f"Failed to download image: {response.status}")
                    image_data = await response.read()

            # Create Twitter API v1.1 client
            auth = tweepy.OAuth1UserHandler(
                consumer_key=self._consumer_key,
                consumer_secret=self._decrypted_consumer_secret,
                access_token=token_data['oauth1']['access_token'],
                access_token_secret=token_data['oauth1']['access_token_secret']
            )
            api = tweepy.API(auth)

            # Upload media
            media = api.media_upload(filename='image', file=image_data)
            
            return str(media.media_id)

        except Exception as e:
            logger.error(f"Error uploading media to Twitter: {str(e)}")
            raise ValueError(f"Failed to upload media: {str(e)}")
    
    async def create_tweet(self, token_data: Dict, content: Dict) -> Dict:
        """
        Create a tweet using Twitter API v2.
        
        Args:
            token_data: Dictionary containing OAuth tokens
            content: Tweet content including text and media_ids
            
        Returns:
            Dictionary containing tweet data
        """
        if 'oauth2' not in token_data:
            raise ValueError("OAuth 2.0 tokens required for creating tweets")
        
        client = tweepy.Client(
            bearer_token=None,
            consumer_key=self._consumer_key,
            consumer_secret=self._decrypted_consumer_secret,
            access_token=token_data['oauth2']['access_token']
        )
        
        # Create tweet with text and media IDs
        tweet = client.create_tweet(
            text=content['text'],
            media_ids=content.get('media_ids')
        )
        
        return {
            'post_id': str(tweet.data['id']),
            'text': tweet.data['text'],
            'platform': 'twitter',
            'url': f"https://twitter.com/i/web/status/{tweet.data['id']}"
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
