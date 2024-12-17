# """
# OAuth Service
# ------------
# A comprehensive OAuth implementation supporting multiple platforms.
# """

# from .core import OAuthBase, TokenManager
# from .platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth

# __version__ = "1.0.0"
# __all__ = [
#     'OAuthBase',
#     'TokenManager',
#     'TwitterOAuth',
#     'LinkedInOAuth',
#     'InstagramOAuth',
#     'FacebookOAuth',
# ]
"""
OAuth Service
------------
A comprehensive OAuth implementation supporting multiple platforms.
"""

# Use lazy imports to break circular dependencies
__version__ = "1.0.0"

def get_oauth_base():
    from .core import get_oauth_base
    return get_oauth_base()

def get_token_manager():
    from .core import get_token_manager
    return get_token_manager()

def get_platforms():
    from .platforms import TwitterOAuth, LinkedInOAuth, InstagramOAuth, FacebookOAuth
    return {
        'TwitterOAuth': TwitterOAuth,
        'LinkedInOAuth': LinkedInOAuth,
        'InstagramOAuth': InstagramOAuth,
        'FacebookOAuth': FacebookOAuth
    }

__all__ = [
    'get_oauth_base',
    'get_token_manager',
    'get_platforms',
]