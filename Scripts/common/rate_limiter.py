"""
Shared rate limiting utilities for congressional trading document processing.
Provides configurable rate limiting for API calls and web scraping.
"""
import time
import requests
from functools import wraps
from typing import Optional, Dict, Any
import logging

class RateLimiter:
    """
    Flexible rate limiter that can be configured for different APIs and use cases.
    """
    
    def __init__(self, calls: int, period: int, name: str = "default"):
        """
        Initialize rate limiter.
        
        Args:
            calls: Number of calls allowed
            period: Time period in seconds
            name: Name for logging purposes
        """
        self.calls = calls
        self.period = period
        self.name = name
        self.call_times = []
        
    def wait_if_needed(self):
        """Wait if necessary to respect rate limit."""
        now = time.time()
        
        # Remove calls outside the current window
        self.call_times = [call_time for call_time in self.call_times 
                          if now - call_time < self.period]
        
        # If we're at the limit, wait
        if len(self.call_times) >= self.calls:
            sleep_time = self.period - (now - self.call_times[0])
            if sleep_time > 0:
                logging.debug(f"Rate limiter '{self.name}': waiting {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        # Record this call
        self.call_times.append(time.time())

    def rate_limited_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """
        Make a rate-limited HTTP request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: URL to request
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
        """
        self.wait_if_needed()
        return requests.request(method, url, **kwargs)

# Pre-configured rate limiters for common use cases
OPENROUTER_LIMITER = RateLimiter(calls=50, period=10, name="OpenRouter")
SENATE_WEB_LIMITER = RateLimiter(calls=1, period=1, name="Senate Web")
HOR_WEB_LIMITER = RateLimiter(calls=10, period=1, name="HOR Web")

def rate_limited_api_call(url: str, headers: Optional[Dict[str, str]] = None, 
                         json: Optional[Dict[str, Any]] = None, 
                         timeout: int = 60, 
                         limiter: Optional[RateLimiter] = None) -> requests.Response:
    """
    Make a rate-limited API call using the appropriate limiter.
    
    Args:
        url: API endpoint URL
        headers: HTTP headers
        json: JSON payload
        timeout: Request timeout
        limiter: Rate limiter to use (defaults to OpenRouter limiter)
        
    Returns:
        Response object
    """
    if limiter is None:
        limiter = OPENROUTER_LIMITER
        
    limiter.wait_if_needed()
    
    return requests.post(url, headers=headers, json=json, timeout=timeout)

def create_rate_limiter(calls: int, period: int, name: str = "custom") -> RateLimiter:
    """
    Create a custom rate limiter with specified parameters.
    
    Args:
        calls: Number of calls allowed
        period: Time period in seconds
        name: Name for logging
        
    Returns:
        Configured RateLimiter instance
    """
    return RateLimiter(calls=calls, period=period, name=name)

# Decorator for automatic rate limiting
def rate_limit(calls: int, period: int):
    """
    Decorator to automatically rate limit function calls.
    
    Args:
        calls: Number of calls allowed
        period: Time period in seconds
    """
    limiter = RateLimiter(calls=calls, period=period, name="decorator")
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed()
            return func(*args, **kwargs)
        return wrapper
    return decorator 