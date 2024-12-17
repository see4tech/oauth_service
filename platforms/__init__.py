"""
Platform-specific OAuth implementations.
"""

from .twitter import TwitterOAuth
from .linkedin import LinkedInOAuth
from .instagram import InstagramOAuth
from .facebook import FacebookOAuth

__all__ = [
    'TwitterOAuth',
    'LinkedInOAuth',
    'InstagramOAuth',
    'FacebookOAuth'
]
