from typing import Dict
import time
import asyncio
from datetime import datetime
import os
from .logger import get_logger

logger = get_logger(__name__)

class RateLimiter:
    """Rate limiting implementation with per-platform configuration."""
    
    def __init__(self, platform: str):
        """
        Initialize rate limiter for specific platform.
        
        Args:
            platform: Platform identifier (e.g., 'twitter', 'facebook')
        """
        self.platform = platform
        self.requests_per_second = float(os.getenv(
            f"{platform.upper()}_RATE_LIMIT",
            "1"  # Default: 1 request per second
        ))
        self.last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
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
