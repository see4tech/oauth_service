"""
Core OAuth functionality.
"""

from .oauth_base import OAuthBase
from .token_manager import TokenManager
from .db import SqliteDB

__all__ = ['OAuthBase', 'TokenManager', 'SqliteDB']
# """
# Core OAuth functionality.
# """

# # Remove direct imports to break potential circular dependencies
# __all__ = ['OAuthBase', 'TokenManager', 'SqliteDB']

# # Lazy import functions to defer module loading
# def get_oauth_base():
#     from .oauth_base import OAuthBase
#     return OAuthBase

# def get_token_manager():
#     from .token_manager import TokenManager
#     return TokenManager

# def get_sqlite_db():
#     from .db import SqliteDB
#     return SqliteDB