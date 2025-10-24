"""
Cache decorators and utilities for frequently accessed data.

Provides decorators for caching function results with TTL and invalidation patterns.
"""
import functools
import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Callable, Dict, Optional, Union
from functools import wraps

from app.services.cache import cache
from app.config import settings

logger = logging.getLogger(__name__)

# Cache TTL configurations
CACHE_TTL_CONFIG = {
    'portfolio_overview': 300,      # 5 minutes - frequently accessed but changes with prices
    'portfolio_holdings': 60,        # 1 minute - changes frequently with real-time updates
    'portfolio_performance': 3600,   # 1 hour - less frequent updates
    'asset_search': 1800,           # 30 minutes - search results
    'asset_prices': 30,             # 30 seconds - real-time prices
    'currency_conversion': 300,      # 5 minutes - exchange rates
    'blockchain_sync': 600,         # 10 minutes - blockchain data
    'cached_metrics': 86400,        # 24 hours - expensive calculations
}

# Cache key generation patterns
CACHE_KEY_PREFIXES = {
    'portfolio_overview': 'portfolio:overview',
    'portfolio_holdings': 'portfolio:holdings',
    'portfolio_performance': 'portfolio:performance',
    'asset_search': 'asset:search',
    'asset_prices': 'asset:prices',
    'currency_conversion': 'currency:fx',
    'blockchain_sync': 'blockchain:sync',
    'cached_metrics': 'metrics:cached',
}


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """
    Generate a deterministic cache key from function arguments.

    Args:
        prefix: Cache key prefix for categorization
        *args, **kwargs: Function arguments to include in key

    Returns:
        Cache key string
    """
    # Create a stable representation of arguments
    key_data = {
        'args': [str(arg) for arg in args],
        'kwargs': {k: str(v) for k, v in sorted(kwargs.items())},
        'timestamp': int(time.time() / 60)  # Bucket by minute to reduce key churn
    }

    # Create hash for consistent key length
    key_string = f"{prefix}:{json.dumps(key_data, sort_keys=True)}"
    key_hash = hashlib.md5(key_string.encode()).hexdigest()[:16]

    return f"{prefix}:{key_hash}"


def cache_result(
    cache_key_prefix: str,
    ttl_seconds: Optional[int] = None,
    invalidate_on_args: Optional[list] = None,
    cache_none: bool = False
):
    """
    Decorator to cache function results with configurable TTL and invalidation.

    Args:
        cache_key_prefix: Prefix for cache key generation
        ttl_seconds: Time to live in seconds, uses config default if None
        invalidate_on_args: List of argument values that should invalidate cache
        cache_none: Whether to cache None results
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Determine TTL
            effective_ttl = ttl_seconds or CACHE_TTL_CONFIG.get(cache_key_prefix, 3600)

            # Generate cache key
            cache_key = generate_cache_key(cache_key_prefix, *args, **kwargs)

            # Check for invalidation arguments
            if invalidate_on_args:
                for arg in invalidate_on_args:
                    if arg in args or arg in kwargs.values():
                        logger.debug(f"Cache invalidation triggered for {cache_key} due to argument: {arg}")
                        break
                else:
                    # Check cache first
                    cached_result = cache.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                        return cached_result

            # Execute function
            try:
                result = await func(*args, **kwargs)

                # Cache the result (including None if configured)
                if result is not None or cache_none:
                    cache.set(cache_key, result, ttl_seconds=effective_ttl)
                    logger.debug(f"Cached result for {func.__name__}: {cache_key} (TTL: {effective_ttl}s)")

                return result

            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Determine TTL
            effective_ttl = ttl_seconds or CACHE_TTL_CONFIG.get(cache_key_prefix, 3600)

            # Generate cache key
            cache_key = generate_cache_key(cache_key_prefix, *args, **kwargs)

            # Check for invalidation arguments
            if invalidate_on_args:
                for arg in invalidate_on_args:
                    if arg in args or arg in kwargs.values():
                        logger.debug(f"Cache invalidation triggered for {cache_key} due to argument: {arg}")
                        break
                else:
                    # Check cache first
                    cached_result = cache.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                        return cached_result

            # Execute function
            try:
                result = func(*args, **kwargs)

                # Cache the result (including None if configured)
                if result is not None or cache_none:
                    cache.set(cache_key, result, ttl_seconds=effective_ttl)
                    logger.debug(f"Cached result for {func.__name__}: {cache_key} (TTL: {effective_ttl}s)")

                return result

            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                raise

        # Return appropriate wrapper based on function signature
        if functools.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_cache(cache_key_prefix: str, *args, **kwargs) -> bool:
    """
    Invalidate cached results for a specific key pattern.

    Args:
        cache_key_prefix: Cache key prefix to invalidate
        *args, **kwargs: Arguments to generate specific cache key

    Returns:
        True if cache was invalidated, False otherwise
    """
    cache_key = generate_cache_key(cache_key_prefix, *args, **kwargs)
    success = cache.delete(cache_key)

    if success:
        logger.debug(f"Invalidated cache: {cache_key}")
    else:
        logger.debug(f"Cache not found for invalidation: {cache_key}")

    return success


def clear_cache_by_pattern(pattern: str) -> int:
    """
    Clear all cached entries matching a pattern.

    Args:
        pattern: Cache key pattern (e.g., "portfolio:*")

    Returns:
        Number of cache entries cleared
    """
    return cache.clear_pattern(pattern)


class CacheManager:
    """Centralized cache management with invalidation strategies."""

    def __init__(self):
        self.cache_patterns = {
            'portfolio_overview': ['portfolio:overview:*'],
            'portfolio_holdings': ['portfolio:holdings:*'],
            'portfolio_performance': ['portfolio:performance:*'],
            'asset_search': ['asset:search:*'],
            'asset_prices': ['asset:prices:*'],
            'currency_conversion': ['currency:fx:*'],
            'blockchain_sync': ['blockchain:sync:*'],
            'cached_metrics': ['metrics:cached:*'],
        }

    def invalidate_portfolio_cache(self, portfolio_id: Optional[str] = None) -> int:
        """
        Invalidate portfolio-related cache entries.

        Args:
            portfolio_id: Specific portfolio ID, None for all portfolios

        Returns:
            Number of cache entries invalidated
        """
        invalidated = 0

        if portfolio_id:
            # Invalidate specific portfolio cache
            patterns = [
                f'portfolio:overview:*{portfolio_id}*',
                f'portfolio:holdings:*{portfolio_id}*',
                f'portfolio:performance:*{portfolio_id}*',
            ]
        else:
            # Invalidate all portfolio cache
            patterns = [
                'portfolio:overview:*',
                'portfolio:holdings:*',
                'portfolio:performance:*',
            ]

        for pattern in patterns:
            count = cache.clear_pattern(pattern)
            invalidated += count

        logger.info(f"Invalidated {invalidated} portfolio cache entries")
        return invalidated

    def invalidate_asset_cache(self, ticker: Optional[str] = None) -> int:
        """
        Invalidate asset-related cache entries.

        Args:
            ticker: Specific ticker, None for all assets

        Returns:
            Number of cache entries invalidated
        """
        if ticker:
            # Invalidate specific asset cache
            cache_key = generate_cache_key('asset:prices', ticker)
            if cache.delete(cache_key):
                return 1
            return 0
        else:
            # Invalidate all asset cache
            return cache.clear_pattern('asset:*')

    def invalidate_all_cache(self) -> int:
        """
        Clear all application cache.

        Returns:
            Number of cache entries cleared
        """
        total_cleared = 0

        for pattern in self.cache_patterns.values():
            for p in pattern:
                count = cache.clear_pattern(p)
                total_cleared += count

        logger.info(f"Cleared {total_cleared} cache entries")
        return total_cleared


# Global cache manager instance
cache_manager = CacheManager()


def cache_with_serialization(
    cache_key_prefix: str,
    ttl_seconds: Optional[int] = None,
    serialize_type: str = 'json'
):
    """
    Decorator that handles serialization/deserialization for complex types.

    Args:
        cache_key_prefix: Prefix for cache key generation
        ttl_seconds: Time to live in seconds
        serialize_type: Serialization method ('json', 'pickle', 'custom')
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = generate_cache_key(cache_key_prefix, *args, **kwargs)

            # Check cache first
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")

                # Deserialize if needed
                if serialize_type == 'json' and isinstance(cached_result, str):
                    try:
                        return json.loads(cached_result)
                    except json.JSONDecodeError:
                        return cached_result
                return cached_result

            # Execute function
            try:
                result = func(*args, **kwargs)

                # Serialize complex types
                if serialize_type == 'json':
                    if isinstance(result, (dict, list, tuple)):
                        serialized = json.dumps(result, default=str)
                    else:
                        serialized = result
                else:
                    serialized = result

                # Cache the result
                effective_ttl = ttl_seconds or CACHE_TTL_CONFIG.get(cache_key_prefix, 3600)
                cache.set(cache_key, serialized, ttl_seconds=effective_ttl)
                logger.debug(f"Cached serialized result for {func.__name__}: {cache_key}")

                return result

            except Exception as e:
                logger.error(f"Error in cached function {func.__name__}: {e}")
                raise

        return wrapper

    return decorator
