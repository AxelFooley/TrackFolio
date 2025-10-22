"""
Rate limiting and caching utilities for news API endpoints.
"""
import time
import hashlib
import json
from typing import Dict, Any, Optional, Callable
from functools import wraps
import logging
from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

logger = logging.getLogger(__name__)


class NewsRateLimiter:
    """Rate limiter for news API endpoints."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests: Dict[str, float] = {}
        self.cleanup_interval = 300  # Clean up every 5 minutes
        self.last_cleanup = time.time()

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed based on rate limit."""
        current_time = time.time()

        # Clean up old entries periodically
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_requests(current_time)
            self.last_cleanup = current_time

        # Check if identifier exists in requests
        if identifier not in self.requests:
            self.requests[identifier] = current_time
            return True

        # Check if request window has passed
        if current_time - self.requests[identifier] >= 60:  # 1 minute window
            self.requests[identifier] = current_time
            return True

        # Check if within rate limit
        request_count = sum(
            1 for timestamp in self.requests.values()
            if current_time - timestamp < 60
        )

        if request_count < self.requests_per_minute:
            self.requests[identifier] = current_time
            return True

        return False

    def _cleanup_old_requests(self, current_time: float) -> None:
        """Remove requests older than 1 minute."""
        old_keys = [
            key for key, timestamp in self.requests.items()
            if current_time - timestamp >= 60
        ]
        for key in old_keys:
            del self.requests[key]


class NewsCache:
    """Redis-based cache for news API responses."""

    def __init__(self, redis_client):
        self.redis = redis_client

    def generate_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate consistent cache key from endpoint and parameters."""
        # Create a deterministic string from parameters
        param_str = json.dumps(params, sort_keys=True, default=str)
        key_hash = hashlib.sha256(f"{endpoint}:{param_str}".encode()).hexdigest()
        return f"news:{endpoint}:{key_hash[:16]}"

    async def get(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached response for given endpoint and parameters."""
        try:
            cache_key = self.generate_cache_key(endpoint, params)
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {endpoint}")
                return json.loads(cached_data)
            logger.debug(f"Cache miss for {endpoint}")
            return None
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")
            return None

    async def set(self, endpoint: str, params: Dict[str, Any],
                 data: Dict[str, Any], ttl: int) -> None:
        """Set cached response with TTL."""
        try:
            cache_key = self.generate_cache_key(endpoint, params)
            cached_data = json.dumps(data, default=str)
            await self.redis.setex(cache_key, ttl, cached_data)
            logger.debug(f"Cached response for {endpoint} with TTL {ttl}s")
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    async def delete(self, endpoint: str, params: Dict[str, Any]) -> None:
        """Delete cached response."""
        try:
            cache_key = self.generate_cache_key(endpoint, params)
            await self.redis.delete(cache_key)
            logger.debug(f"Deleted cache for {endpoint}")
        except Exception as e:
            logger.warning(f"Cache delete failed: {e}")


# Global instances
news_rate_limiter = NewsRateLimiter(settings.news_rate_limit_requests_per_minute)


async def get_redis_client():
    """Get Redis client from database configuration."""
    from app.database import get_redis
    return await get_redis()


def rate_limit_news_endpoint(max_requests: int = None):
    """Decorator for rate limiting news API endpoints."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Use client IP as identifier for rate limiting
            client_ip = request.client.host if request.client else "unknown"

            # Check if request is allowed
            if not news_rate_limiter.is_allowed(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Rate limit exceeded",
                        "message": f"Too many requests. Limit: {max_requests or settings.news_rate_limit_requests_per_minute} requests per minute",
                        "retry_after": 60
                    }
                )

            return await func(request, *args, **kwargs)
        return wrapper
    return decorator


class NewsRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware for news API rate limiting."""

    async def dispatch(self, request: Request, call_next):
        # Only apply rate limiting to news API endpoints
        if not request.url.path.startswith("/api/news"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Check rate limit
        if not news_rate_limiter.is_allowed(client_ip):
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {settings.news_rate_limit_requests_per_minute} requests per minute",
                    "retry_after": 60
                }
            )

        response = await call_next(request)
        return response


def cache_news_response(ttl_seconds: int = None):
    """Decorator for caching news API responses."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(request: Request, *args, **kwargs):
            # Generate parameters from function arguments
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(request, *args, **kwargs)
            bound_args.apply_defaults()

            # Extract parameters for cache key
            params = {}
            for param_name, param_value in bound_args.arguments.items():
                if param_name not in ['request', 'self'] and not param_name.startswith('_'):
                    if hasattr(param_value, 'dict'):
                        # Handle Pydantic models
                        params[param_name] = param_value.dict()
                    else:
                        params[param_name] = str(param_value)

            # Get endpoint name from function
            endpoint_name = func.__name__

            # Get Redis client
            redis_client = await get_redis_client()
            cache = NewsCache(redis_client)

            # Try to get cached response
            cached_response = await cache.get(endpoint_name, params)
            if cached_response:
                return cached_response

            # Execute function and cache result
            response = await func(request, *args, **kwargs)

            # Cache the response if it's successful
            if hasattr(response, 'status_code') and response.status_code < 400:
                cache_ttl = ttl_seconds or settings.news_cache_ttl_seconds
                await cache.set(endpoint_name, params, response.body, cache_ttl)

            return response
        return wrapper
    return decorator