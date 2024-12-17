"""
OAuth Service
------------
A comprehensive OAuth implementation supporting multiple platforms.
"""

from .core import OAuthBase, TokenManager
from .platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth

__version__ = "1.0.0"
__all__ = [
    'OAuthBase',
    'TokenManager',
    'TwitterOAuth',
    'LinkedInOAuth',
    'InstagramOAuth',
    'FacebookOAuth',
]
