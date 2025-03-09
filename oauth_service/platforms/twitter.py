from typing import Dict, Optional, List
import tweepy
from requests_oauthlib import OAuth2Session
import aiohttp
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger
from ..core.db import SqliteDB
from ..utils.crypto import generate_api_key
from fastapi import HTTPException
import base64
import os
import hashlib
from datetime import datetime
from urllib.parse import urlencode
from requests_oauthlib import OAuth1Session
import tempfile
import requests
from io import BytesIO
import json
from ..core.token_refresh_handler import refresh_handler

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
        
        # Store the base callback URL and create version-specific URLs
        base_url = callback_url.rstrip('/')
        if '/callback/1' in base_url:
            base_url = base_url.replace('/callback/1', '')
        elif '/callback/2' in base_url:
            base_url = base_url.replace('/callback/2', '')
        elif '/callback' in base_url:
            base_url = base_url.replace('/callback', '')
        
        self.oauth1_callback = f"{base_url}/callback/1"
        self.oauth2_callback = f"{base_url}/callback/2"
        
        # OAuth 1.0a setup
        self.oauth1_handler = tweepy.OAuthHandler(
            self._consumer_key,
            self._decrypted_consumer_secret,
            self.oauth1_callback  # Use OAuth 1.0a specific callback
        )
        
        # OAuth 2.0 setup with offline.access scope for refresh tokens
        self.oauth2_client = OAuth2Session(
            client_id=self.client_id,
            redirect_uri=self.oauth2_callback,  # Use OAuth 2.0 specific callback
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
                'redirect_uri': self.oauth2_callback,  # Use the OAuth 2.0 specific callback
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
        tokens = {}  # Initialize tokens dictionary
        
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
                'redirect_uri': self.oauth2_callback,  # Use OAuth 2.0 specific callback
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
                    
                    return tokens  # Return tokens here for OAuth 2.0
                
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
    
    async def refresh_token(self, token_data: Dict, x_api_key: Optional[str] = None) -> Dict:
        """Refresh an expired OAuth 2.0 token.
        
        Args:
            token_data: Dictionary containing the refresh token
            x_api_key: Optional API key for validation
            
        Returns:
            Dict: New token data with refreshed access token
        """
        try:
            logger.debug("\n=== Twitter OAuth2 Token Refresh ===")
            logger.debug(f"Token data keys available: {list(token_data.keys())}")
            
            refresh_token = token_data.get('refresh_token')
            if not refresh_token:
                logger.error("No refresh token found in token data")
                return None
                
            logger.debug(f"Refresh token found: {refresh_token[:5]}...{refresh_token[-5:] if len(refresh_token) > 10 else ''}")
            
            # Prepare token refresh parameters
            token_url = "https://api.twitter.com/2/oauth2/token"
            refresh_params = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self.client_id,
            }
            
            # Create basic auth header with client_id and client_secret
            auth_string = f"{self.client_id}:{self._decrypted_client_secret}"
            b64_auth = base64.b64encode(auth_string.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            
            logger.debug("Making token refresh request with params:")
            logger.debug(f"URL: {token_url}")
            logger.debug(f"Headers: {{'Authorization': 'Basic ***', 'Content-Type': '{headers['Content-Type']}'}}")
            logger.debug(f"Refresh params: {{'grant_type': '{refresh_params['grant_type']}', 'refresh_token': '***', 'client_id': '{refresh_params['client_id']}'}}")
            
            # Make token refresh request
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=refresh_params, headers=headers) as response:
                    response_text = await response.text()
                    logger.debug(f"Token refresh response status: {response.status}")
                    logger.debug(f"Token refresh response headers: {dict(response.headers)}")
                    
                    # Sanitize the response text to avoid logging tokens
                    safe_response = response_text
                    if response.status == 200 and "access_token" in response_text:
                        try:
                            resp_json = json.loads(response_text)
                            if "access_token" in resp_json:
                                access_token = resp_json["access_token"]
                                safe_response = response_text.replace(access_token, "[REDACTED_ACCESS_TOKEN]")
                            if "refresh_token" in resp_json:
                                refresh_token = resp_json["refresh_token"]
                                safe_response = safe_response.replace(refresh_token, "[REDACTED_REFRESH_TOKEN]")
                        except json.JSONDecodeError:
                            pass
                    
                    logger.debug(f"Token refresh response (sanitized): {safe_response}")
                    
                    if response.status != 200:
                        logger.error(f"Token refresh failed with status {response.status}")
                        logger.error(f"Error response: {response_text}")
                        return None
                        
                    try:
                        new_token_data = json.loads(response_text)
                        logger.debug(f"Successfully parsed token response")
                        logger.debug(f"New token data keys: {list(new_token_data.keys())}")
                        logger.debug(f"Has new access_token: {bool(new_token_data.get('access_token'))}")
                        logger.debug(f"Has new refresh_token: {bool(new_token_data.get('refresh_token'))}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse token response: {str(e)}")
                        return None
                    
            # Keep the token_type if it exists
            if 'token_type' in token_data:
                new_token_data['token_type'] = token_data['token_type']
                
            # Calculate expires_at
            if 'expires_in' in new_token_data:
                expires_in = new_token_data['expires_in']
                expires_at = int(datetime.utcnow().timestamp() + expires_in)
                new_token_data['expires_at'] = expires_at
                logger.debug(f"Token expires in {expires_in} seconds (at timestamp {expires_at})")
                
            logger.debug("Successfully refreshed Twitter OAuth2 token")
            return new_token_data
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            logger.error("Stack trace:", exc_info=True)
            return None
    
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
            logger.debug("\n=== Starting Media Upload Process ===")
            logger.debug(f"Token data structure: {list(token_data.keys())}")
            
            # First check if we have OAuth 1.0a tokens
            if not isinstance(token_data, dict):
                logger.error("Token data is not a dictionary")
                logger.error(f"Received type: {type(token_data)}")
                raise ValueError("Invalid token data structure")
                
            if 'oauth1' not in token_data:
                logger.error("OAuth 1.0a tokens not found in token data")
                logger.error(f"Available keys: {list(token_data.keys())}")
                raise ValueError("OAuth 1.0a tokens required for media upload")
            
            oauth1_tokens = token_data['oauth1']
            if not isinstance(oauth1_tokens, dict):
                logger.error("OAuth 1.0a token data is not a dictionary")
                logger.error(f"Received type: {type(oauth1_tokens)}")
                raise ValueError("Invalid OAuth 1.0a token structure")
                
            logger.debug(f"OAuth1 token keys: {list(oauth1_tokens.keys())}")
            
            if not oauth1_tokens.get('access_token'):
                logger.error("Missing access_token in OAuth1 tokens")
                raise ValueError("Missing OAuth 1.0a access token")
                
            if not oauth1_tokens.get('token_secret'):
                logger.error("Missing token_secret in OAuth1 tokens")
                raise ValueError("Missing OAuth 1.0a token secret")

            # Create OAuth1 auth object for requests
            from requests_oauthlib import OAuth1
            oauth1_auth = OAuth1(
                self._consumer_key,
                client_secret=self._decrypted_consumer_secret,
                resource_owner_key=oauth1_tokens['access_token'],
                resource_owner_secret=oauth1_tokens['token_secret']
            )
            
            logger.debug("OAuth1 authentication object created successfully")
            
            # Download image and save temporarily
            logger.debug("2. Downloading image")
            logger.debug(f"   URL: {image_url}")

            response = requests.get(image_url)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name

            try:
                content_type = response.headers.get('content-type', 'image/jpeg')
                size_mb = len(response.content) / (1024 * 1024)
                
                logger.debug(f"3. Image downloaded")
                logger.debug(f"   Content-Type: {content_type}")
                logger.debug(f"   Size: {size_mb:.2f}MB")
                logger.debug(f"   Temp file: {tmp_path}")
                
                if size_mb > 5:
                    logger.debug("Image too large for simple upload, needs chunked upload")
                    raise ValueError("Image too large (>5MB), needs chunked upload")
                
                # Upload to Twitter using requests directly
                upload_url = "https://upload.twitter.com/1.1/media/upload.json"
                
                with open(tmp_path, 'rb') as media_file:
                    files = {
                        'media': ('media.jpg', media_file, content_type)
                    }
                    response = requests.post(upload_url, auth=oauth1_auth, files=files)
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            logger.debug(f"5. Got response: {response.status_code}")
            logger.debug("Received response from Twitter API")
            
            if response.status_code != 200:
                raise ValueError(f"Failed to upload media: {response.text}")
            
            media_data = response.json()
            media_id = media_data['media_id_string']
            logger.debug(f"6. Success! Media ID: {media_id}")
            return media_id

        except Exception as e:
            logger.error(f"Error uploading media to Twitter: {str(e)}")
            raise ValueError(f"Failed to upload media: {str(e)}")
    
    async def create_post(self, token_data: Dict, content: Dict, user_id: str = None, x_api_key: str = None) -> Dict:
        """Create a tweet using Twitter API v2."""
        try:
            logger.debug("\n=== Starting Tweet Creation Process ===")
            logger.debug(f"User ID from payload: {user_id}")
            logger.debug(f"Has x-api-key: {'yes' if x_api_key else 'no'}")
            if x_api_key:
                logger.debug(f"x-api-key: {x_api_key[:5]}...{x_api_key[-5:] if len(x_api_key) > 10 else ''}")
            logger.debug(f"Token data keys: {list(token_data.keys())}")
            
            if not user_id:
                logger.error("No user_id provided in payload")
                raise ValueError("User ID is required")
            
            logger.debug(f"Using user_id: {user_id}")
            
            # First, validate and refresh OAuth2 token if needed
            logger.debug(f"\n=== OAuth2 Token Validation ===")
            logger.debug(f"Getting OAuth 2.0 token for user {user_id}")
            
            # Log the API key being used for token validation
            db = SqliteDB()
            stored_api_key = db.get_user_api_key(user_id, "twitter-oauth2")
            if stored_api_key:
                logger.debug(f"Found stored OAuth2 API key: {stored_api_key[:5]}...{stored_api_key[-5:] if len(stored_api_key) > 10 else ''}")
                logger.debug(f"OAuth2 API key matches provided x-api-key: {stored_api_key == x_api_key}")
            else:
                logger.debug("No OAuth2 API key found in database")
            
            oauth2_token_data = await refresh_handler.get_valid_token(user_id, "twitter-oauth2", x_api_key)
            if not oauth2_token_data:
                logger.error("Failed to get valid OAuth 2.0 token")
                
                # Check if token exists but couldn't be refreshed
                token_manager = TokenManager()
                raw_token = await token_manager.get_token("twitter-oauth2", user_id)
                if raw_token:
                    logger.error(f"Token exists but refresh failed. Token keys: {list(raw_token.keys())}")
                    if 'expires_at' in raw_token:
                        now = datetime.utcnow().timestamp()
                        logger.error(f"Token expired: {raw_token['expires_at'] < now} (Expires at: {raw_token['expires_at']}, Now: {now})")
                    if 'refresh_token' in raw_token:
                        logger.error(f"Refresh token exists but refresh operation failed")
                    else:
                        logger.error(f"No refresh token available")
                else:
                    logger.error("No token found in database")
                
                raise ValueError("Failed to get valid OAuth 2.0 token")
            
            logger.debug(f"OAuth 2.0 token data keys: {list(oauth2_token_data.keys())}")
            
            # Extract OAuth 2.0 token
            oauth2_token = oauth2_token_data.get('access_token')
            if not oauth2_token:
                logger.error("OAuth 2.0 access token not found in token data")
                raise ValueError("OAuth 2.0 access token not found")
            
            logger.debug(f"OAuth2 token first 10 chars: {oauth2_token[:10]}...")
            
            # Now that we have a valid OAuth2 token, proceed with media upload if needed
            media_ids = None
            if content.get('image_url'):
                # Get OAuth 1.0a tokens
                logger.debug(f"\n=== OAuth1 Token Validation for Media Upload ===")
                
                # Log the API key being used for OAuth1 token validation
                stored_oauth1_api_key = db.get_user_api_key(user_id, "twitter-oauth1")
                if stored_oauth1_api_key:
                    logger.debug(f"Found stored OAuth1 API key: {stored_oauth1_api_key[:5]}...{stored_oauth1_api_key[-5:] if len(stored_oauth1_api_key) > 10 else ''}")
                    logger.debug(f"OAuth1 API key matches provided x-api-key: {stored_oauth1_api_key == x_api_key}")
                else:
                    logger.debug("No OAuth1 API key found in database")
                
                oauth1_token_data = await refresh_handler.get_valid_token(user_id, "twitter-oauth1", x_api_key)
                if not oauth1_token_data:
                    logger.error("OAuth 1.0a tokens required but not found")
                    
                    # Check if token exists
                    token_manager = TokenManager()
                    raw_oauth1_token = await token_manager.get_token("twitter-oauth1", user_id)
                    if raw_oauth1_token:
                        logger.error(f"OAuth1 token exists but validation failed. Token keys: {list(raw_oauth1_token.keys())}")
                    else:
                        logger.error("No OAuth1 token found in database")
                    
                    raise ValueError("OAuth 1.0a tokens required for media upload")
                
                logger.debug(f"OAuth1 token data keys: {list(oauth1_token_data.keys())}")
                
                # Wrap OAuth1 tokens in the expected structure
                oauth1_wrapped = {'oauth1': oauth1_token_data}
                logger.debug(f"Wrapped OAuth1 token data keys: {list(oauth1_wrapped.keys())}")
                logger.debug(f"Inner OAuth1 token data keys: {list(oauth1_token_data.keys())}")
                
                try:
                    media_id = await self.upload_media_v1(oauth1_wrapped, content['image_url'])
                    media_ids = [media_id]
                    logger.debug(f"Media uploaded successfully with ID: {media_id}")
                except Exception as e:
                    logger.error(f"Media upload failed: {str(e)}")
                    raise ValueError(f"Media upload failed: {str(e)}")
            
            # Create tweet using OAuth 2.0 User Context
            logger.debug("\n=== Creating Tweet ===")
            logger.debug("Using OAuth 2.0 User Context")
            
            tweet_data = {
                "text": content['text']
            }
            if media_ids:
                tweet_data["media"] = {"media_ids": media_ids}
                logger.debug(f"Including media in tweet: {media_ids}")
            
            logger.debug(f"Tweet data: {tweet_data}")
            
            # Use the session to make the request
            async with aiohttp.ClientSession() as session:
                # Clean token for header (remove Bearer prefix if present)
                clean_token = oauth2_token.replace("Bearer ", "")
                
                headers = {
                    'Authorization': f'Bearer {clean_token}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'v2TweetPoster'
                }
                
                logger.debug("\n=== Request Details ===")
                logger.debug(f"URL: https://api.twitter.com/2/tweets")
                logger.debug(f"Headers: {{'Authorization': 'Bearer {clean_token[:5]}...{clean_token[-5:] if len(clean_token) > 10 else ''}', 'Content-Type': '{headers['Content-Type']}', 'User-Agent': '{headers['User-Agent']}'}}")
                logger.debug(f"Data: {tweet_data}")
                
                # Make the request with OAuth 2.0 User Context
                async with session.post(
                    "https://api.twitter.com/2/tweets",
                    headers=headers,
                    json=tweet_data
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"\n=== Twitter API Response ===")
                    logger.debug(f"Status code: {response.status}")
                    logger.debug(f"Response headers: {dict(response.headers)}")
                    logger.debug(f"Response text: {response_text}")
                    
                    if response.status != 201:
                        # Sanitize error message in case it contains tokens
                        safe_error = response_text.replace(clean_token, '[REDACTED]') if clean_token in response_text else response_text
                        raise ValueError(f"Failed to create tweet: {safe_error}")
                    
                    tweet = await response.json()
                    
                    if not tweet or 'data' not in tweet:
                        raise ValueError("Invalid response from Twitter API")
                    
                    logger.debug("Tweet created successfully")
                    return {
                        'post_id': str(tweet['data']['id']),
                        'text': tweet['data']['text'],
                        'platform': 'twitter',
                        'url': f"https://twitter.com/i/web/status/{tweet['data']['id']}"
                    }
                    
        except Exception as e:
            # Ensure no tokens are logged in the error
            error_msg = str(e)
            if 'oauth2_token' in locals() and oauth2_token and oauth2_token in error_msg:
                error_msg = error_msg.replace(oauth2_token, '[REDACTED]')
            logger.error(f"Error creating tweet: {error_msg}")
            # Log the stack trace for better debugging
            logger.error("Stack trace:", exc_info=True)
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
    
    async def post_tweet(self, access_token: str, text: str, oauth_version: str = "oauth2") -> Dict:
        """Post a tweet using either OAuth 1.0a or 2.0."""
        try:
            if oauth_version == "oauth2":
                # OAuth 2.0 tweet endpoint
                url = "https://api.twitter.com/2/tweets"
                headers = {
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                }
                data = {"text": text}
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=data) as response:
                        if response.status != 201:
                            error_text = await response.text()
                            raise ValueError(f"Failed to post tweet: {error_text}")
                        return await response.json()
                            
            else:  # OAuth 1.0a
                # Create OAuth1 session with access token
                auth = OAuth1Session(
                    self._consumer_key,
                    client_secret=self._decrypted_consumer_secret,
                    resource_owner_key=access_token['access_token'],
                    resource_owner_secret=access_token['access_token_secret']
                )
                
                url = "https://api.twitter.com/1.1/statuses/update.json"
                data = {"status": text}
                
                response = await auth.post(url, data=data)
                if response.status != 200:
                    raise ValueError(f"Failed to post tweet: {await response.text()}")
                return await response.json()
                
        except Exception as e:
            logger.error(f"Error posting tweet: {str(e)}")
            raise
    
    async def post_tweet_with_media(self, user_id: str, text: str, image_url: str) -> Dict:
        """Post tweet with media using both API versions."""
        try:
            logger.debug("\n=== Starting Tweet with Media Process ===")
            logger.debug(f"User ID: {user_id}")
            logger.debug(f"Has text: {'yes' if text else 'no'}")
            logger.debug(f"Image URL: {image_url}")
            
            # Get tokens for both versions
            logger.debug("1. Getting tokens from TokenManager")
            token_manager = TokenManager()
            try:
                tokens = await token_manager.get_token("twitter", user_id)
                logger.debug("2. Got tokens from TokenManager")
                logger.debug("Token details:")
                logger.debug(f"Raw tokens: {tokens}")  # Let's see the actual token data
                logger.debug(f"Type: {type(tokens)}")
                if isinstance(tokens, dict):
                    logger.debug(f"Keys: {list(tokens.keys())}")
                    if 'oauth2' in tokens:
                        oauth2_data = tokens['oauth2']
                        logger.debug(f"OAuth2 data type: {type(oauth2_data)}")
                        if isinstance(oauth2_data, dict):
                            logger.debug(f"OAuth2 keys: {list(oauth2_data.keys())}")
            except Exception as e:
                logger.error(f"Error getting tokens: {str(e)}")
                logger.error(f"Token manager error details:", exc_info=True)
                raise
            
            if not tokens or not isinstance(tokens, dict):
                raise ValueError("No valid tokens found")
            
            # 1. Upload media using v1.1 API with OAuth 1.0a tokens
            oauth1_tokens = tokens.get('oauth1')
            if not oauth1_tokens:
                raise ValueError("OAuth 1.0a tokens not found")
            
            media_id = await self._upload_media_v1(oauth1_tokens, image_url)
            logger.debug(f"Media uploaded successfully with ID: {media_id}")
            
            # 2. Post tweet with media using v2 API with OAuth 2.0 tokens
            oauth2_tokens = tokens.get('oauth2')
            logger.debug(f"\nChecking OAuth2 tokens:")
            logger.debug(f"Full tokens structure: {tokens}")  # This will show us the full token structure
            logger.debug(f"oauth2_tokens value: {oauth2_tokens}")  # This will show us what we got from .get('oauth2')
            if isinstance(oauth2_tokens, dict):
                logger.debug(f"OAuth2 tokens keys: {oauth2_tokens.keys()}")
                access_token = oauth2_tokens.get('access_token')
                logger.debug(f"Access token found: {'yes' if access_token else 'no'}")
            else:
                logger.debug(f"OAuth2 tokens is not a dict")
                access_token = oauth2_tokens
            
            if not access_token:
                logger.error(f"OAuth2 token data missing or invalid:")
                logger.error(f"  oauth2_tokens type: {type(oauth2_tokens)}")
                logger.error(f"  oauth2_tokens keys: {oauth2_tokens.keys() if isinstance(oauth2_tokens, dict) else 'N/A'}")
                raise ValueError("OAuth 2.0 access token not found in token data")
            
            logger.debug("Posting tweet with media")
            logger.debug(f"Using OAuth2 token: {access_token[:10]}...")
            logger.debug(f"Media ID: {media_id}")
            
            return await self._post_tweet_v2(access_token, text, media_id)
            
        except Exception as e:
            logger.error(f"Error creating tweet with media: {str(e)}")
            raise
    
    async def _upload_media_v1(self, oauth1_tokens: Dict, image_url: str) -> str:
        """Upload media using Twitter v1.1 API."""
        try:
            logger.debug("\n=== Media Upload Process ===")
            logger.debug("OAuth1 credentials configured")
            logger.debug(f"OAuth1 token keys: {list(oauth1_tokens.keys())}")
            
            # Create OAuth1 auth object for requests
            from requests_oauthlib import OAuth1
            oauth1_auth = OAuth1(
                self._consumer_key,
                client_secret=self._decrypted_consumer_secret,
                resource_owner_key=oauth1_tokens['access_token'],
                resource_owner_secret=oauth1_tokens['token_secret']
            )
            
            logger.debug("2. Downloading image")
            logger.debug(f"   URL: {image_url}")
            
            # Download image and save temporarily
            response = requests.get(image_url)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name

            try:
                content_type = response.headers.get('content-type', 'image/jpeg')
                size_mb = len(response.content) / (1024 * 1024)
                
                logger.debug(f"3. Image downloaded")
                logger.debug(f"   Content-Type: {content_type}")
                logger.debug(f"   Size: {size_mb:.2f}MB")
                logger.debug(f"   Temp file: {tmp_path}")
                
                if size_mb > 5:
                    logger.debug("Image too large for simple upload, needs chunked upload")
                    raise ValueError("Image too large (>5MB), needs chunked upload")
                
                # Upload to Twitter using requests directly
                upload_url = "https://upload.twitter.com/1.1/media/upload.json"
                
                with open(tmp_path, 'rb') as media_file:
                    files = {
                        'media': ('media.jpg', media_file, content_type)
                    }
                    response = requests.post(upload_url, auth=oauth1_auth, files=files)
            finally:
                # Clean up temp file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            logger.debug(f"5. Got response: {response.status_code}")
            logger.debug("Received response from Twitter API")
            
            if response.status_code != 200:
                raise ValueError(f"Failed to upload media: {response.text}")
            
            media_data = response.json()
            media_id = media_data['media_id_string']
            logger.debug(f"6. Success! Media ID: {media_id}")
            return media_id

        except Exception as e:
            logger.error(f"Error uploading media to Twitter: {str(e)}")
            raise ValueError(f"Failed to upload media: {str(e)}")
    
    async def _post_tweet_v2(self, access_token: str, text: str, media_id: str) -> Dict:
        """Post tweet with media using Twitter v2 API."""
        url = "https://api.twitter.com/2/tweets"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "media": {
                "media_ids": [media_id]
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 201:
                    error_text = await response.text()
                    raise ValueError(f"Failed to post tweet: {error_text}")
                return await response.json()