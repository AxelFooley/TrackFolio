"""
Cache service for application data.

Provides Redis-backed caching with TTL support for frequently accessed data.
"""
import json
import logging
from typing import Any, Optional
import redis
from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Manage application-level caching with Redis."""

    def __init__(self):
        """Initialize Redis connection from environment variables."""
        try:
            # Parse Redis URL: redis://[password@]host[:port]/[db]
            self.redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                socket_keepalive_options={1: 1},
            )
            # Test connection
            self.redis_client.ping()
            self.available = True
            logger.info("Cache service initialized successfully")
        except Exception as e:
            self.available = False
            logger.warning(f"Cache service unavailable: {str(e)}")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value (deserialized from JSON) or None if not found/cache unavailable
        """
        if not self.available:
            return None

        try:
            value = self.redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except Exception as e:
            logger.debug(f"Cache get error for key {key}: {str(e)}")
            return None

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """
        Set value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl_seconds: Time to live in seconds (default: 1 hour)

        Returns:
            True if successful, False otherwise
        """
        if not self.available:
            return False

        try:
            serialized = json.dumps(value)
            self.redis_client.setex(key, ttl_seconds, serialized)
            return True
        except Exception as e:
            logger.debug(f"Cache set error for key {key}: {str(e)}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete value from cache.

        Args:
            key: Cache key

        Returns:
            True if key was deleted, False otherwise
        """
        if not self.available:
            return False

        try:
            return self.redis_client.delete(key) > 0
        except Exception as e:
            logger.debug(f"Cache delete error for key {key}: {str(e)}")
            return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.

        Args:
            pattern: Redis key pattern (e.g., "asset_search:*")

        Returns:
            Number of keys deleted
        """
        if not self.available:
            return 0

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                return self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.debug(f"Cache clear_pattern error for {pattern}: {str(e)}")
            return 0


# Global cache instance
cache = CacheService()
