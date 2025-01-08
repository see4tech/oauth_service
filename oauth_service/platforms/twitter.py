from typing import Dict, Optional, List
import tweepy
from requests_oauthlib import OAuth2Session
import aiohttp
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger
from fastapi import HTTPException
import base64
import os
import hashlib
from datetime import datetime
from urllib.parse import urlencode

logger = get_logger(__name__)

class TwitterOAuth(OAuthBase):
    """Twitter OAuth implementation supporting both OAuth 1.0a and OAuth 2.0."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str, consumer_key: str = None, consumer_secret: str = None):
        """Initialize Twitter OAuth with both OAuth 1.0a and 2.0 credentials."""
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="twitter")
        
        # Store OAuth 1.0a credentials separately
        self._consumer_key = consumer_key or client_id
        self._consumer_secret = consumer_secret or client_secret
        
        # Decrypt OAuth 2.0 client secret
        self._decrypted_client_secret = self.crypto.decrypt(self._client_secret)
        
        # For OAuth 1.0a, use raw secrets as they come from settings
        self._decrypted_consumer_secret = self._consumer_secret
        
        # Store the callback URL exactly as provided - don't modify it
        self.callback_url = callback_url
        
        # OAuth 2.0 setup with offline.access scope for refresh tokens
        self.oauth2_client = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=callback_url,  # Use the exact callback URL
            scope=['tweet.read', 'tweet.write', 'users.read', 'offline.access']
        )
    
    async def get_authorization_url(self) -> Dict[str, str]:
        """Get authorization URLs for both OAuth 1.0a and OAuth 2.0."""
        try:
            # Get OAuth 1.0a URL
            oauth1_url = self.oauth1_handler.get_authorization_url()
            
            # Get OAuth 2.0 URL with PKCE
            code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
            code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).decode('utf-8').rstrip('=')
            
            # Create Basic Auth header
            auth_string = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
            basic_auth = base64.b64encode(auth_string.encode()).decode()
            
            # Add required parameters for OAuth 2.0
            extra_params = {
                'response_type': 'code',
                'client_id': self.client_id,
                'redirect_uri': self.callback_url,  # Don't modify the callback URL here
                'scope': 'tweet.read tweet.write users.read offline.access',
                'code_challenge': code_challenge,
                'code_challenge_method': 'S256',
                'access_type': 'offline',  # Request refresh token
                'prompt': 'consent'  # Force consent screen
            }
            
            headers = {
                'Authorization': f'Basic {basic_auth}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            authorization_url = 'https://twitter.com/i/oauth2/authorize'
            
            # Build URL with parameters
            query_params = urlencode(extra_params)
            oauth2_url = f"{authorization_url}?{query_params}"
            
            logger.debug("Generated OAuth 2.0 authorization URL with parameters:")
            logger.debug(f"- Authorization URL: {oauth2_url}")
            logger.debug(f"- Scopes: {extra_params['scope']}")
            logger.debug(f"- Code challenge method: {extra_params['code_challenge_method']}")
            logger.debug(f"- Redirect URI: {extra_params['redirect_uri']}")
            
            logger.debug(f"Twitter redirect URI for auth: {self.callback_url}")
            
            return {
                'oauth1_url': oauth1_url,
                'oauth2_url': oauth2_url,
                'code_verifier': code_verifier,  # Save for token exchange
                'headers': headers  # Include headers for token exchange
            }
            
        except Exception as e:
            logger.error(f"Error getting authorization URL: {str(e)}")
            raise
    
    async def get_access_token(self, 
                             oauth2_code: Optional[str] = None,
                             oauth1_verifier: Optional[str] = None,
                             code_verifier: Optional[str] = None) -> Dict:
        """Exchange authorization codes for access tokens."""
        try:
            logger.debug("Starting OAuth 2.0 token exchange")
            logger.debug(f"Code verifier present: {bool(code_verifier)}")
            
            # Create Basic Auth header
            auth_string = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
            basic_auth = base64.b64encode(auth_string.encode()).decode()
            
            # Set up token exchange parameters
            token_data = {
                'code': oauth2_code,
                'grant_type': 'authorization_code',
                'redirect_uri': self.callback_url,  # Use the same callback URL as authorization
                'code_verifier': code_verifier
            }
            
            headers = {
                'Authorization': f'Basic {basic_auth}',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            logger.debug(f"Token exchange URL: https://api.twitter.com/2/oauth2/token")
            logger.debug(f"Token exchange data: {token_data}")
            logger.debug(f"Token exchange headers: {headers}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    'https://api.twitter.com/2/oauth2/token',
                    data=token_data,
                    headers=headers
                ) as response:
                    if not response.ok:
                        error_text = await response.text()
                        logger.error(f"Token exchange failed with status {response.status}: {error_text}")
                        raise ValueError(f"Token exchange failed: {error_text}")
                    
                    token = await response.json()
                    
                    # Log token response for debugging
                    logger.debug(f"OAuth 2.0 token response keys: {list(token.keys())}")
                    logger.debug(f"OAuth 2.0 token response scopes: {token.get('scope', '')}")
                    logger.debug(f"Has refresh_token: {bool(token.get('refresh_token'))}")
                    
                    tokens['oauth2'] = {
                        'access_token': token['access_token'],
                        'refresh_token': token.get('refresh_token'),
                        'expires_in': token.get('expires_in', 7200),
                        'expires_at': token.get('expires_at', datetime.utcnow().timestamp() + token.get('expires_in', 7200))
                    }
                    
                    logger.debug(f"OAuth 2.0 tokens obtained successfully. Has refresh token: {bool(tokens['oauth2'].get('refresh_token'))}")
            
        except Exception as e:
            logger.error(f"Error exchanging OAuth 2.0 code: {str(e)}")
            raise
        
        if oauth1_verifier:
            try:
                # Create a new OAuth1 handler with the stored request token
                if self.callback_url.endswith('/callback'):
                    base_callback = self.callback_url
                else:
                    base_callback = self.callback_url.rstrip('/') + '/callback'
                oauth1_callback = base_callback + '/1'
                
                oauth1_handler = tweepy.OAuthHandler(
                    self._consumer_key,
                    self._decrypted_consumer_secret,
                    oauth1_callback
                )
                
                # Set the request token and secret
                oauth1_handler.request_token = {
                    'oauth_token': tokens.get('oauth1_request_token'),
                    'oauth_token_secret': tokens.get('oauth1_request_token_secret')
                }
                
                # Get the access token
                oauth1_handler.get_access_token(oauth1_verifier)
                tokens['oauth1'] = {
                    'access_token': oauth1_handler.access_token,
                    'access_token_secret': oauth1_handler.access_token_secret
                }
                logger.debug("OAuth 1.0a tokens obtained successfully")
            except Exception as e:
                logger.error(f"Error exchanging OAuth 1.0a verifier: {str(e)}")
                raise
        
        # Log token structure (without sensitive data)
        logger.debug(f"Final token structure: {list(tokens.keys())}")
        return tokens
    
    async def refresh_token(self, refresh_token: str) -> Dict:
        """
        Refresh OAuth 2.0 access token.
        
        Args:
            refresh_token: Refresh token from previous authorization
            
        Returns:
            Dictionary containing new access token data
        """
        try:
            logger.debug("Attempting to refresh Twitter OAuth 2.0 token")
            
            # Create a new OAuth2Session for the refresh
            refresh_session = OAuth2Session(
                client_id=self.client_id,
                scope=['tweet.read', 'tweet.write', 'users.read', 'offline.access']
            )
            
            # Log refresh attempt details
            logger.debug(f"Refresh token length: {len(refresh_token)}")
            logger.debug(f"Client ID length: {len(self.client_id)}")
            logger.debug(f"Client secret length: {len(self._decrypted_client_secret)}")
            
            # Refresh the token
            token = refresh_session.refresh_token(
                'https://api.twitter.com/2/oauth2/token',
                refresh_token=refresh_token,
                client_id=self.client_id,
                client_secret=self._decrypted_client_secret,
                include_client_id=True
            )
            
            # Log token response for debugging
            logger.debug(f"Refresh token response keys: {list(token.keys())}")
            logger.debug(f"Refresh token response scopes: {token.get('scope', '')}")
            logger.debug(f"New refresh token received: {bool(token.get('refresh_token'))}")
            
            # Ensure we have required fields
            if 'access_token' not in token:
                raise ValueError("Refresh response missing access_token")
            
            return {
                'oauth2': {
                    'access_token': token['access_token'],
                    'refresh_token': token.get('refresh_token', refresh_token),  # Use old refresh token if new one not provided
                    'expires_in': token.get('expires_in', 7200),
                    'expires_at': token.get('expires_at', datetime.utcnow().timestamp() + token.get('expires_in', 7200))
                }
            }
            
        except Exception as e:
            logger.error(f"Error refreshing Twitter OAuth 2.0 token: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise
    
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
            logger.debug("Starting media upload process")
            logger.debug(f"Token data structure: {list(token_data.keys() if isinstance(token_data, dict) else [])}")
            
            # First check if we have OAuth 1.0a tokens
            if not isinstance(token_data, dict):
                logger.error("Token data is not a dictionary")
                raise ValueError("Invalid token data structure")
                
            if 'oauth1' not in token_data:
                logger.error("OAuth 1.0a tokens not found in token data")
                raise ValueError("OAuth 1.0a tokens required for media upload")
            
            oauth1_tokens = token_data['oauth1']
            if not isinstance(oauth1_tokens, dict):
                logger.error("OAuth 1.0a token data is not a dictionary")
                raise ValueError("Invalid OAuth 1.0a token structure")
                
            if not oauth1_tokens.get('access_token') or not oauth1_tokens.get('access_token_secret'):
                logger.error("Missing required OAuth 1.0a token components")
                raise ValueError("Missing OAuth 1.0a access token or secret")

            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as response:
                    if not response.ok:
                        raise ValueError(f"Failed to download image: {response.status}")
                    image_data = await response.read()

            logger.debug("Image downloaded successfully")

            # Create Twitter API v1.1 client
            auth = tweepy.OAuth1UserHandler(
                consumer_key=self._consumer_key,
                consumer_secret=self._decrypted_consumer_secret,
                access_token=oauth1_tokens['access_token'],
                access_token_secret=oauth1_tokens['access_token_secret']
            )
            api = tweepy.API(auth)

            # Upload media
            media = api.media_upload(filename='image', file=image_data)
            logger.debug(f"Successfully uploaded media with ID: {media.media_id}")
            
            return str(media.media_id)

        except ValueError as e:
            logger.error(f"Validation error in media upload: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error uploading media to Twitter: {str(e)}")
            raise ValueError(f"Failed to upload media: {str(e)}")
    
    async def create_post(self, token_data: Dict, content: Dict) -> Dict:
        """
        Create a tweet using Twitter API v2.
        
        Args:
            token_data: Dictionary containing OAuth tokens
            content: Tweet content including text and media_ids
            
        Returns:
            Dictionary containing tweet data
        """
        try:
            logger.debug("Starting tweet creation process")
            logger.debug(f"Token data structure: {token_data.keys()}")
            
            # For media upload, we need OAuth 1.0a tokens
            media_ids = None
            if content.get('image_url'):
                if not isinstance(token_data, dict) or 'oauth1' not in token_data:
                    logger.error("OAuth 1.0a tokens required but not found")
                    raise ValueError("OAuth 1.0a tokens required for media upload")
                
                try:
                    media_id = await self.upload_media_v1(token_data, content['image_url'])
                    media_ids = [media_id]
                    logger.debug(f"Media uploaded successfully with ID: {media_id}")
                except Exception as e:
                    logger.error(f"Media upload failed: {str(e)}")
                    raise ValueError(f"Media upload failed: {str(e)}")

            # For creating the tweet, prefer OAuth 2.0 but fall back to OAuth 1.0a if needed
            if isinstance(token_data, dict) and 'oauth2' in token_data:
                oauth2_data = token_data['oauth2']
                oauth2_token = oauth2_data.get('access_token')
                if not oauth2_token:
                    raise ValueError("OAuth 2.0 access token not found")
                
                client = tweepy.Client(
                    bearer_token=None,
                    consumer_key=self._consumer_key,
                    consumer_secret=self._decrypted_consumer_secret,
                    access_token=oauth2_token
                )
            elif isinstance(token_data, dict) and 'oauth1' in token_data:
                oauth1_data = token_data['oauth1']
                if not oauth1_data.get('access_token') or not oauth1_data.get('access_token_secret'):
                    raise ValueError("OAuth 1.0a tokens incomplete")
                
                client = tweepy.Client(
                    bearer_token=None,
                    consumer_key=self._consumer_key,
                    consumer_secret=self._decrypted_consumer_secret,
                    access_token=oauth1_data['access_token'],
                    access_token_secret=oauth1_data['access_token_secret']
                )
            else:
                raise ValueError("No valid OAuth tokens found")
            
            # Create the tweet
            tweet = client.create_tweet(
                text=content['text'],
                media_ids=media_ids
            )
            
            if not tweet or not tweet.data:
                raise ValueError("Failed to create tweet")
            
            logger.debug("Tweet created successfully")
            return {
                'post_id': str(tweet.data['id']),
                'text': tweet.data['text'],
                'platform': 'twitter',
                'url': f"https://twitter.com/i/web/status/{tweet.data['id']}"
            }
            
        except Exception as e:
            logger.error(f"Error creating tweet: {str(e)}")
            raise
    
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
    
    async def initialize_oauth1(self, callback_url: str) -> Dict:
        """Initialize OAuth 1.0a flow."""
        try:
            logger.debug(f"Initializing OAuth 1.0a with callback URL: {callback_url}")
            
            # Create OAuth1Session for request token
            oauth = OAuth1Session(
                self.client_id,
                client_secret=self.client_secret,
                callback_uri=callback_url
            )
            
            # Get request token
            request_token_url = "https://api.twitter.com/oauth/request_token"
            try:
                response = await oauth.fetch_request_token(request_token_url)
                oauth_token = response.get('oauth_token')
                oauth_token_secret = response.get('oauth_token_secret')
                logger.debug(f"Obtained request token: {oauth_token[:10]}...")
                
                # Generate authorization URL
                auth_url = f"https://api.twitter.com/oauth/authorize?oauth_token={oauth_token}"
                
                return {
                    'oauth1_url': auth_url,
                    'oauth_token': oauth_token,
                    'oauth_token_secret': oauth_token_secret
                }
            except Exception as e:
                logger.error(f"Error getting request token: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error initializing OAuth 1.0a: {str(e)}")
            raise
    
    async def get_oauth1_access_token(self, oauth_token: str, oauth_verifier: str) -> Dict:
        """Exchange OAuth 1.0a verifier for access token."""
        try:
            logger.debug("=== Twitter OAuth 1.0a Token Exchange ===")
            logger.debug(f"OAuth token: {oauth_token[:10]}...")
            logger.debug(f"OAuth verifier: {oauth_verifier[:10]}...")
            
            # Create OAuth1Session with request token
            oauth = tweepy.OAuth1UserHandler(
                consumer_key=self._consumer_key,
                consumer_secret=self._decrypted_consumer_secret,
                callback=self.callback_url
            )
            
            # Set the request token
            oauth.request_token = {
                'oauth_token': oauth_token,
                'oauth_token_secret': oauth_verifier
            }
            
            try:
                # Get the access token
                access_token, access_token_secret = oauth.get_access_token(oauth_verifier)
                logger.debug("Successfully obtained OAuth 1.0a access tokens")
                
                return {
                    'access_token': access_token,
                    'access_token_secret': access_token_secret
                }
                
            except Exception as e:
                logger.error(f"Error getting access token: {str(e)}")
                raise
                
        except Exception as e:
            logger.error(f"Error in OAuth 1.0a token exchange: {str(e)}")
            raise