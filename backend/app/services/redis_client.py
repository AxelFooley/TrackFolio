"""Shared Redis client factory for the application.

Centralizes Redis client initialization to avoid duplication across services.
Provides a single source of truth for Redis connection configuration and error handling.
"""
import logging
from typing import Optional

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from app.config import settings

logger = logging.getLogger(__name__)

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Get or initialize shared Redis client with graceful fallback.

    Implements lazy initialization pattern to avoid connection overhead
    if Redis is not needed. Returns None if Redis is unavailable or
    connection fails.

    Returns:
        Redis client instance or None if Redis is unavailable or connection failed

    Example:
        >>> redis_client = get_redis_client()
        >>> if redis_client:
        ...     redis_client.set("key", "value")
    """
    global _redis_client

    if not REDIS_AVAILABLE:
        return None

    if _redis_client is None:
        try:
            _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
            # Test connection
            _redis_client.ping()
            logger.debug("Redis client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis client: {e}")
            _redis_client = None

    return _redis_client


def reset_redis_client() -> None:
    """Reset the global Redis client.

    Used for testing to ensure a clean state between tests.
    """
    global _redis_client
    _redis_client = None


def close_redis_client() -> None:
    """Close the global Redis client connection.

    Properly closes the Redis connection to avoid connection leaks.
    Should be called during application shutdown.
    """
    global _redis_client
    if _redis_client:
        try:
            _redis_client.close()
            logger.debug("Redis client closed successfully")
        except Exception as e:
            logger.warning(f"Error closing Redis client: {e}")
        finally:
            _redis_client = None
