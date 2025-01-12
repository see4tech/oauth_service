from typing import Dict
import time
import asyncio
from datetime import datetime
import os
from .logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """Rate limiting implementation with per-platform configuration."""
    
    # Platform-specific default rate limits (requests per second)
    DEFAULT_RATE_LIMITS = {
        "linkedin": 1.0,    # General LinkedIn API
        "linkedin_token_exchange": 1.67,  # 100 requests per minute = 1.67 requests per second
        "twitter": 1.0,    # Conservative default
        "facebook": 1.0,   # Conservative default
        "instagram": 1.0   # Conservative default
    }
    
    def __init__(self, platform: str):
        """
        Initialize rate limiter for specific platform.
        
        Args:
            platform: Platform identifier (e.g., 'twitter', 'facebook')
        """
        self.platform = platform
        # Use platform-specific default if available, otherwise use 1 req/sec
        default_rate = self.DEFAULT_RATE_LIMITS.get(platform, 1.0)
        self.requests_per_second = float(os.getenv(
            f"{platform.upper()}_RATE_LIMIT",
            str(default_rate)
        ))
        self.last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        
        logger.debug(f"Initialized rate limiter for {platform} with {self.requests_per_second} requests/second")
    
    async def wait(self, endpoint: str) -> None:
        """
        Wait if necessary to respect rate limits.
        
        Args:
            endpoint: API endpoint identifier
        """
        async with self._lock:
            current_time = time.time()
            key = f"{self.platform}:{endpoint}"
            
            if key in self.last_request_time:
                time_since_last_request = current_time - self.last_request_time[key]
                if time_since_last_request < (1 / self.requests_per_second):
                    wait_time = (1 / self.requests_per_second) - time_since_last_request
                    logger.debug(
                        f"Rate limit wait for {self.platform}:{endpoint}: {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
            
            self.last_request_time[key] = time.time()
    
    async def reset(self, endpoint: str) -> None:
        """
        Reset rate limit tracking for endpoint.
        
        Args:
            endpoint: API endpoint identifier
        """
        async with self._lock:
            key = f"{self.platform}:{endpoint}"
            if key in self.last_request_time:
                del self.last_request_time[key]
