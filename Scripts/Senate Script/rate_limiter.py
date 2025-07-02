import time
import requests
from functools import wraps

def rate_limited_api_call(url, **kwargs):
    """Make an API call with rate limiting."""
    time.sleep(1)  # Basic rate limiting - 1 second between calls
    return requests.post(url, **kwargs) 