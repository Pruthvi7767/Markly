"""Exponential backoff and retry helper.

Implements exponential backoff with jitter and capped attempts to prevent
network errors or rate limits from consuming turns.
"""
import time
import random
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_with_backoff(max_attempts=3, base_delay=1.0, max_delay=10.0, exceptions=(Exception,)):
    """Decorator to retry a function with exponential backoff and jitter."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error("All %d retry attempts failed for %s. Error: %s", max_attempts, func.__name__, e)
                        raise
                    
                    # Exponential delay with jitter
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    jitter = delay * random.uniform(0.1, 0.3)
                    sleep_time = delay + jitter
                    logger.warning(
                        "Attempt %d failed for %s. Retrying in %.2f seconds. Error: %s",
                        attempt, func.__name__, sleep_time, e
                    )
                    time.sleep(sleep_time)
        return wrapper
    return decorator
