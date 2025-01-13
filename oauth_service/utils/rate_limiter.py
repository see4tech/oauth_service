from typing import Dict, List
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
        self.request_timestamps: Dict[str, List[float]] = {}  # Store timestamps for each endpoint
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
            
            # Initialize timestamps list if not exists
            if key not in self.request_timestamps:
                self.request_timestamps[key] = []
            
            # Remove timestamps older than 1 minute
            window_start = current_time - 60
            self.request_timestamps[key] = [
                ts for ts in self.request_timestamps[key] if ts > window_start
            ]
            
            # For LinkedIn token exchange, enforce the 100 requests per minute limit
            if self.platform == "linkedin_token_exchange":
                requests_in_window = len(self.request_timestamps[key])
                if requests_in_window >= 100:
                    # Calculate wait time until oldest request expires from window
                    wait_time = 60 - (current_time - self.request_timestamps[key][0])
                    logger.debug(
                        f"Rate limit exceeded for {self.platform}:{endpoint}. "
                        f"Requests in last minute: {requests_in_window}. "
                        f"Waiting {wait_time:.2f}s"
                    )
                    await asyncio.sleep(wait_time)
                    # After waiting, remove expired timestamps
                    window_start = time.time() - 60
                    self.request_timestamps[key] = [
                        ts for ts in self.request_timestamps[key] if ts > window_start
                    ]
            else:
                # For other endpoints, enforce requests per second
                if self.request_timestamps[key]:
                    time_since_last_request = current_time - self.request_timestamps[key][-1]
                    if time_since_last_request < (1 / self.requests_per_second):
                        wait_time = (1 / self.requests_per_second) - time_since_last_request
                        logger.debug(
                            f"Rate limit wait for {self.platform}:{endpoint}: {wait_time:.2f}s"
                        )
                        await asyncio.sleep(wait_time)
            
            # Add current timestamp
            self.request_timestamps[key].append(time.time())
    
    async def reset(self, endpoint: str) -> None:
        """
        Reset rate limit tracking for endpoint.
        
        Args:
            endpoint: API endpoint identifier
        """
        async with self._lock:
            key = f"{self.platform}:{endpoint}"
            if key in self.request_timestamps:
                self.request_timestamps[key] = []
