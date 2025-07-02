import requests
from ratelimit import limits, sleep_and_retry

# Rate limiting decorator - 50 requests per 10 seconds
CALLS = 50
RATE_LIMIT_PERIOD = 10

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT_PERIOD)
def rate_limited_api_call(*args, **kwargs):
    """Wrapper for rate-limited API calls"""
    return requests.post(*args, **kwargs) 