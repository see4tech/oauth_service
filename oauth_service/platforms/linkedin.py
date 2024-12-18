# from typing import Dict, Optional, List
# import aiohttp
# from fastapi import HTTPException
# import json
# import base64
# from urllib.parse import urlencode
# from ..core.oauth_base import OAuthBase
# from ..utils.rate_limiter import RateLimiter
# from ..utils.logger import get_logger

# logger = get_logger(__name__)

# class LinkedInOAuth(OAuthBase):
#     """LinkedIn OAuth 2.0 implementation."""
    
#     def __init__(self, client_id: str, client_secret: str, callback_url: str):
#         """
#         Initialize LinkedIn OAuth handler.
        
#         Args:
#             client_id: LinkedIn application client ID
#             client_secret: LinkedIn application client secret
#             callback_url: OAuth callback URL
#         """
#         super().__init__(client_id, client_secret, callback_url)
#         self.rate_limiter = RateLimiter(platform="linkedin")
#         self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
#         self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
#         self.api_url = "https://api.linkedin.com/v2"
#         logger.debug(f"Initialized LinkedIn OAuth with callback URL: {callback_url}")
    
#     async def get_authorization_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None) -> str:
#         """
#         Get LinkedIn authorization URL.
        
#         Args:
#             state: Optional state parameter for CSRF protection
#             scopes: Optional list of scopes to request
            
#         Returns:
#             Authorization URL string
#         """
#         try:
#             scope_str = " ".join(scopes) if scopes else "r_liteprofile w_member_social"
            
#             params = {
#                 "response_type": "code",
#                 "client_id": self.client_id,
#                 "redirect_uri": self.callback_url,
#                 "state": state,
#                 "scope": scope_str
#             }
            
#             logger.debug(f"Building authorization URL with scopes: {scope_str}")
#             logger.debug(f"Authorization parameters: {params}")
            
#             query = urlencode(params)
#             auth_url = f"{self.auth_url}?{query}"
            
#             logger.debug(f"Generated authorization URL: {auth_url}")
#             return auth_url
            
#         except Exception as e:
#             logger.error(f"Error generating authorization URL: {str(e)}")
#             raise HTTPException(
#                 status_code=500,
#                 detail=f"Error generating authorization URL: {str(e)}"
#             )
#     async def get_access_token(self, code: str) -> Dict:
#         """
#         Exchange authorization code for access token.
#         """
#         try:
#             logger.debug(f"Exchanging code for access token. Code: {code[:10]}...")
            
#             # Prepare request data
#             data = {
#                 "grant_type": "authorization_code",
#                 "code": code,
#                 "client_id": self.client_id,
#                 "client_secret": self.crypto.decrypt(self._client_secret),
#                 "redirect_uri": self.callback_url
#             }
            
#             # Log request data (excluding secret)
#             debug_data = dict(data)
#             debug_data['client_secret'] = '[REDACTED]'
#             logger.debug(f"Request data (excluding secret): {debug_data}")
            
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(
#                     self.token_url,
#                     data=data,
#                     headers={
#                         'Content-Type': 'application/x-www-form-urlencoded',
#                         'Accept': 'application/json'
#                     }
#                 ) as response:
#                     logger.debug(f"Token response status: {response.status}")
#                     response_text = await response.text()
#                     logger.debug(f"Token response text: {response_text}")
                    
#                     if not response.ok:
#                         raise HTTPException(
#                             status_code=response.status,
#                             detail=f"LinkedIn token exchange failed: {response_text}"
#                         )
                    
#                     data = json.loads(response_text)
#                     return {
#                         "access_token": data["access_token"],
#                         "expires_in": data.get("expires_in", 3600),
#                         "refresh_token": data.get("refresh_token")
#                     }
                    
#         except Exception as e:
#             logger.error(f"Error exchanging code for token: {str(e)}")
#             raise HTTPException(
#                 status_code=500,
#                 detail=f"Error exchanging code for token: {str(e)}"
#             )    
#     # async def get_access_token(self, code: str) -> Dict:
#     #     """
#     #     Exchange authorization code for access token.
        
#     #     Args:
#     #         code: Authorization code from callback
            
#     #     Returns:
#     #         Dictionary containing access token and related data
#     #     """
#     #     try:
#     #         logger.debug(f"Exchanging code for access token. Code: {code[:10]}...")
            
#     #         # Create basic auth header
#     #         auth_str = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
#     #         auth_header = base64.b64encode(auth_str.encode()).decode()
            
#     #         # Prepare request data
#     #         data = {
#     #             "grant_type": "authorization_code",
#     #             "code": code,
#     #             "redirect_uri": self.callback_url
#     #         }
            
#     #         # Log request data
#     #         debug_data = dict(data)
#     #         logger.debug(f"Request data: {debug_data}")
#     #         logger.debug(f"Using client_id: {self.client_id}")
#     #         logger.debug(f"Redirect URI: {self.callback_url}")
            
#     #         async with aiohttp.ClientSession() as session:
#     #             async with session.post(
#     #                 self.token_url,
#     #                 data=urlencode(data),
#     #                 headers={
#     #                     'Content-Type': 'application/x-www-form-urlencoded',
#     #                     'Accept': 'application/json',
#     #                     'Authorization': f'Basic {auth_header}'
#     #                 }
#     #             ) as response:
#     #                 logger.debug(f"Token response status: {response.status}")
#     #                 response_text = await response.text()
#     #                 logger.debug(f"Token response text: {response_text}")
                    
#     #                 if not response.ok:
#     #                     raise HTTPException(
#     #                         status_code=response.status,
#     #                         detail=f"LinkedIn token exchange failed: {response_text}"
#     #                     )
                    
#     #                 try:
#     #                     data = json.loads(response_text)
#     #                     return {
#     #                         "access_token": data["access_token"],
#     #                         "expires_in": data.get("expires_in", 3600),
#     #                         "refresh_token": data.get("refresh_token")
#     #                     }
#     #                 except (json.JSONDecodeError, KeyError) as e:
#     #                     logger.error(f"Error parsing token response: {str(e)}")
#     #                     raise HTTPException(
#     #                         status_code=500,
#     #                         detail=f"Invalid response format: {str(e)}"
#     #                     )
                    
#     #     except Exception as e:
#     #         logger.error(f"Error exchanging code for token: {str(e)}")
#     #         raise HTTPException(
#     #             status_code=500,
#     #             detail=f"Error exchanging code for token: {str(e)}"
#     #         )
    
#     async def refresh_token(self, refresh_token: str) -> Dict:
#         """
#         Refresh access token.
        
#         Args:
#             refresh_token: Refresh token from previous authorization
            
#         Returns:
#             Dictionary containing new access token data
#         """
#         try:
#             logger.debug("Attempting to refresh LinkedIn access token")
            
#             # Create basic auth header
#             auth_str = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
#             auth_header = base64.b64encode(auth_str.encode()).decode()
            
#             data = {
#                 "grant_type": "refresh_token",
#                 "refresh_token": refresh_token
#             }
            
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(
#                     self.token_url,
#                     data=urlencode(data),
#                     headers={
#                         'Content-Type': 'application/x-www-form-urlencoded',
#                         'Accept': 'application/json',
#                         'Authorization': f'Basic {auth_header}'
#                     }
#                 ) as response:
#                     response_text = await response.text()
#                     logger.debug(f"Refresh token response status: {response.status}")
                    
#                     if not response.ok:
#                         raise HTTPException(
#                             status_code=response.status,
#                             detail=f"Token refresh failed: {response_text}"
#                         )
                    
#                     data = json.loads(response_text)
#                     return {
#                         "access_token": data["access_token"],
#                         "expires_in": data.get("expires_in", 3600),
#                         "refresh_token": data.get("refresh_token")
#                     }
                    
#         except Exception as e:
#             logger.error(f"Error refreshing token: {str(e)}")
#             raise HTTPException(
#                 status_code=500,
#                 detail=f"Error refreshing token: {str(e)}"
#             )

#     async def get_profile(self, token: str) -> Dict:
#         """
#         Get user profile information.
        
#         Args:
#             token: Access token
            
#         Returns:
#             Dictionary containing user profile data
#         """
#         try:
#             headers = {
#                 "Authorization": f"Bearer {token}",
#                 "Content-Type": "application/json",
#                 "X-Restli-Protocol-Version": "2.0.0"
#             }
            
#             logger.debug("Fetching LinkedIn user profile")
            
#             async with aiohttp.ClientSession() as session:
#                 async with session.get(
#                     f"{self.api_url}/me",
#                     headers=headers,
#                     params={
#                         "projection": "(id,firstName,lastName,profilePicture(displayImage~:playableStreams))"
#                     }
#                 ) as response:
#                     response_text = await response.text()
#                     logger.debug(f"Profile response status: {response.status}")
                    
#                     if not response.ok:
#                         raise HTTPException(
#                             status_code=response.status,
#                             detail=f"Failed to fetch profile: {response_text}"
#                         )
                    
#                     return json.loads(response_text)
                    
#         except Exception as e:
#             logger.error(f"Error fetching profile: {str(e)}")
#             raise HTTPException(
#                 status_code=500,
#                 detail=f"Error fetching profile: {str(e)}"
#             )

#     async def create_post(self, token: str, content: Dict) -> Dict:
#         """
#         Create a LinkedIn post.
        
#         Args:
#             token: Access token
#             content: Post content dictionary
            
#         Returns:
#             Dictionary containing post ID and status
#         """
#         try:
#             headers = {
#                 "Authorization": f"Bearer {token}",
#                 "Content-Type": "application/json",
#                 "X-Restli-Protocol-Version": "2.0.0"
#             }
            
#             # Get user profile to get person ID
#             profile = await self.get_profile(token)
#             person_id = profile.get("id")
            
#             if not person_id:
#                 raise HTTPException(
#                     status_code=500,
#                     detail="Could not determine user ID for post"
#                 )
            
#             post_data = {
#                 "author": f"urn:li:person:{person_id}",
#                 "lifecycleState": "PUBLISHED",
#                 "specificContent": {
#                     "com.linkedin.ugc.ShareContent": {
#                         "shareCommentary": {
#                             "text": content.get("text", "")
#                         },
#                         "shareMediaCategory": "NONE"
#                     }
#                 },
#                 "visibility": {
#                     "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
#                 }
#             }
            
#             logger.debug(f"Creating LinkedIn post for user: {person_id}")
            
#             async with aiohttp.ClientSession() as session:
#                 async with session.post(
#                     f"{self.api_url}/ugcPosts",
#                     headers=headers,
#                     json=post_data
#                 ) as response:
#                     response_text = await response.text()
#                     logger.debug(f"Post creation response status: {response.status}")
                    
#                     if not response.ok:
#                         raise HTTPException(
#                             status_code=response.status,
#                             detail=f"Failed to create post: {response_text}"
#                         )
                    
#                     data = json.loads(response_text)
#                     return {
#                         "post_id": data["id"],
#                         "status": "published",
#                         "platform": "linkedin"
#                     }
                    
#         except Exception as e:
#             logger.error(f"Error creating post: {str(e)}")
#             raise HTTPException(
#                 status_code=500,
#                 detail=f"Error creating post: {str(e)}"
#             )
from typing import Dict, Optional, List
import aiohttp
from fastapi import HTTPException
import json
import base64
from urllib.parse import urlencode
from ..core.oauth_base import OAuthBase
from ..utils.rate_limiter import RateLimiter
from ..utils.logger import get_logger

logger = get_logger(__name__)

class LinkedInOAuth(OAuthBase):
    """LinkedIn OAuth 2.0 implementation."""
    
    def __init__(self, client_id: str, client_secret: str, callback_url: str):
        """
        Initialize LinkedIn OAuth handler.
        
        Args:
            client_id: LinkedIn application client ID
            client_secret: LinkedIn application client secret
            callback_url: OAuth callback URL
        """
        super().__init__(client_id, client_secret, callback_url)
        self.rate_limiter = RateLimiter(platform="linkedin")
        self.auth_url = "https://www.linkedin.com/oauth/v2/authorization"
        self.token_url = "https://www.linkedin.com/oauth/v2/accessToken"
        self.api_url = "https://api.linkedin.com/v2"
        logger.debug(f"Initialized LinkedIn OAuth with callback URL: {callback_url}")
    
    async def get_authorization_url(self, state: Optional[str] = None, scopes: Optional[List[str]] = None) -> str:
        """
        Get LinkedIn authorization URL.
        
        Args:
            state: Optional state parameter for CSRF protection
            scopes: Optional list of scopes to request
            
        Returns:
            Authorization URL string
        """
        try:
            scope_str = " ".join(scopes) if scopes else "r_liteprofile w_member_social"
            
            params = {
                "response_type": "code",
                "client_id": self.client_id,
                "redirect_uri": self.callback_url,
                "state": state,
                "scope": scope_str
            }
            
            logger.debug(f"Building authorization URL with scopes: {scope_str}")
            logger.debug(f"Authorization parameters: {params}")
            
            query = urlencode(params)
            auth_url = f"{self.auth_url}?{query}"
            
            logger.debug(f"Generated authorization URL: {auth_url}")
            return auth_url
            
        except Exception as e:
            logger.error(f"Error generating authorization URL: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error generating authorization URL: {str(e)}"
            )

    async def get_access_token(self, code: str) -> Dict:
        """
        Exchange authorization code for access token.
        """
        try:
            logger.debug(f"Exchanging code for access token. Code: {code[:10]}...")
            
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.crypto.decrypt(self._client_secret),
                "redirect_uri": self.callback_url
            }
            
            debug_data = dict(data)
            debug_data['client_secret'] = '[REDACTED]'
            logger.debug(f"Request data (excluding secret): {debug_data}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    data=data,
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json'
                    }
                ) as response:
                    logger.debug(f"Token response status: {response.status}")
                    response_text = await response.text()
                    logger.debug(f"Token response text: {response_text}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"LinkedIn token exchange failed: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return {
                        "access_token": data["access_token"],
                        "expires_in": data.get("expires_in", 3600),
                        "refresh_token": data.get("refresh_token")
                    }
                    
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error exchanging code for token: {str(e)}"
            )
    
    async def refresh_token(self, refresh_token: str) -> Dict:
        """
        Refresh access token.
        
        Args:
            refresh_token: Refresh token from previous authorization
            
        Returns:
            Dictionary containing new access token data
        """
        try:
            logger.debug("Attempting to refresh LinkedIn access token")
            
            auth_str = f"{self.client_id}:{self.crypto.decrypt(self._client_secret)}"
            auth_header = base64.b64encode(auth_str.encode()).decode()
            
            data = {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.token_url,
                    data=urlencode(data),
                    headers={
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'Accept': 'application/json',
                        'Authorization': f'Basic {auth_header}'
                    }
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Refresh token response status: {response.status}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Token refresh failed: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return {
                        "access_token": data["access_token"],
                        "expires_in": data.get("expires_in", 3600),
                        "refresh_token": data.get("refresh_token")
                    }
                    
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error refreshing token: {str(e)}"
            )

    async def create_post(self, token: str, content: Dict) -> Dict:
        """
        Create a LinkedIn post.
        
        Args:
            token: Access token
            content: Post content dictionary
            
        Returns:
            Dictionary containing post ID and status
        """
        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            
            post_data = {
                "author": "urn:li:person:me",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": content.get("text", "")
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                }
            }
            
            logger.debug("Creating LinkedIn post")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/ugcPosts",
                    headers=headers,
                    json=post_data
                ) as response:
                    response_text = await response.text()
                    logger.debug(f"Post creation response status: {response.status}")
                    
                    if not response.ok:
                        raise HTTPException(
                            status_code=response.status,
                            detail=f"Failed to create post: {response_text}"
                        )
                    
                    data = json.loads(response_text)
                    return {
                        "post_id": data["id"],
                        "status": "published",
                        "platform": "linkedin"
                    }
                    
        except Exception as e:
            logger.error(f"Error creating post: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creating post: {str(e)}"
            )