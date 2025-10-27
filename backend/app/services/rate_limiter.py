"""
Rate limiting service for API endpoints.

Implements decorator-based rate limiting using Redis as the backend for distributed
rate limiting across multiple instances. Supports configurable request limits and
time windows per endpoint.
"""
import logging
import time
from functools import wraps
from typing import Callable, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from app.services.cache import cache
from app.config import settings

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int, limit: int, window: int):
        """
        Initialize rate limit exception.

        Args:
            retry_after: Seconds until the client can retry
            limit: Request limit for the window
            window: Time window in seconds
        """
        super().__init__(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} requests per {window} seconds"
        )
        self.retry_after = retry_after
        self.limit = limit
        self.window = window


class RateLimiter:
    """Rate limiter for API endpoints using Redis backend."""

    @staticmethod
    def _get_client_identifier(request: Request) -> str:
        """
        Get unique identifier for client (user ID or IP address).

        Args:
            request: FastAPI request object

        Returns:
            Unique client identifier
        """
        # Try to get user ID from request scope
        user_id = request.scope.get("user_id")
        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    @staticmethod
    def _get_rate_limit_key(endpoint: str, client_id: str) -> str:
        """
        Generate Redis key for rate limit tracking.

        Args:
            endpoint: API endpoint name
            client_id: Unique client identifier

        Returns:
            Redis key for rate limit
        """
        return f"rate_limit:{endpoint}:{client_id}"

    @staticmethod
    def _get_reset_key(endpoint: str, client_id: str) -> str:
        """
        Generate Redis key for rate limit window reset time.

        Args:
            endpoint: API endpoint name
            client_id: Unique client identifier

        Returns:
            Redis key for reset timestamp
        """
        return f"rate_limit_reset:{endpoint}:{client_id}"

    @staticmethod
    def check_rate_limit(
        endpoint: str,
        client_id: str,
        limit: int,
        window: int
    ) -> tuple[int, int, Optional[int]]:
        """
        Check if client has exceeded rate limit.

        Args:
            endpoint: API endpoint name
            client_id: Unique client identifier
            limit: Maximum requests allowed in window
            window: Time window in seconds

        Returns:
            Tuple of (remaining_requests, limit, retry_after_seconds or None)
            - remaining_requests: Number of requests left in current window
            - limit: Maximum requests allowed
            - retry_after_seconds: Seconds until next request, or None if not exceeded

        Raises:
            RateLimitExceeded: If limit is exceeded
        """
        if not cache.available:
            logger.warning("Cache unavailable, skipping rate limit check")
            return limit, limit, None

        rate_limit_key = RateLimiter._get_rate_limit_key(endpoint, client_id)
        reset_key = RateLimiter._get_reset_key(endpoint, client_id)

        try:
            # Get current count and reset time
            current_count = cache.redis_client.get(rate_limit_key)
            reset_time = cache.redis_client.get(reset_key)

            now = int(time.time())

            if reset_time is None:
                # First request in this window
                reset_time = now + window
                cache.redis_client.setex(rate_limit_key, window, "1")
                cache.redis_client.setex(reset_key, window, str(reset_time))
                remaining = limit - 1
                return remaining, limit, None

            reset_timestamp = int(reset_time)

            if now > reset_timestamp:
                # Window has expired, reset counter
                reset_time = now + window
                cache.redis_client.setex(rate_limit_key, window, "1")
                cache.redis_client.setex(reset_key, window, str(reset_time))
                remaining = limit - 1
                return remaining, limit, None

            # Window still active, increment counter
            count = int(current_count) if current_count else 0
            count += 1

            if count > limit:
                # Limit exceeded
                retry_after = reset_timestamp - now
                raise RateLimitExceeded(retry_after, limit, window)

            # Update counter
            ttl = reset_timestamp - now
            cache.redis_client.setex(rate_limit_key, max(ttl, 1), str(count))

            remaining = limit - count
            return remaining, limit, None

        except RateLimitExceeded:
            raise
        except Exception as e:
            logger.error(f"Rate limit check error: {str(e)}", exc_info=True)
            # Fail open - allow request if rate limiter fails
            return limit, limit, None

    @staticmethod
    async def add_rate_limit_headers(
        response: JSONResponse,
        limit: int,
        remaining: int,
        reset_time: Optional[int] = None
) -> JSONResponse:
        """
        Add X-RateLimit headers to response.

        Args:
            response: FastAPI response object
            limit: Maximum requests in window
            remaining: Remaining requests in current window
            reset_time: Unix timestamp when limit resets (optional)

        Returns:
            Response with rate limit headers added
        """
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        if reset_time is not None:
            response.headers["X-RateLimit-Reset"] = str(reset_time)

        return response


def rate_limit(
    requests: int = 100,
    window_seconds: int = 60,
    endpoint_name: Optional[str] = None
) -> Callable:
    """
    Decorator for rate limiting async endpoints.

    Args:
        requests: Maximum number of requests allowed in the time window
        window_seconds: Time window in seconds
        endpoint_name: Optional custom endpoint name for Redis key (defaults to function name)

    Returns:
        Decorator function

    Example:
        @rate_limit(requests=50, window_seconds=60)
        async def get_unified_overview(db: AsyncSession):
            ...
    """
    def decorator(func: Callable) -> Callable:
        endpoint = endpoint_name or func.__name__

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract Request object from kwargs or args
            request: Optional[Request] = kwargs.get("request")

            if request is None:
                # Try to find request in args (common pattern with FastAPI dependencies)
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                # No request object found, skip rate limiting
                logger.debug(f"No request object found for {endpoint}, skipping rate limit")
                return await func(*args, **kwargs)

            client_id = RateLimiter._get_client_identifier(request)

            try:
                remaining, limit, retry_after = RateLimiter.check_rate_limit(
                    endpoint=endpoint,
                    client_id=client_id,
                    limit=requests,
                    window=window_seconds
                )

                # Call the actual endpoint
                response = await func(*args, **kwargs)

                # Add rate limit headers to response
                if hasattr(response, 'headers'):
                    response.headers["X-RateLimit-Limit"] = str(limit)
                    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

                    # Calculate reset time for headers
                    reset_key = RateLimiter._get_reset_key(endpoint, client_id)
                    reset_time = cache.redis_client.get(reset_key)
                    if reset_time:
                        response.headers["X-RateLimit-Reset"] = str(reset_time)

                return response

            except RateLimitExceeded as e:
                # Return 429 response with headers
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": e.detail,
                        "retry_after": e.retry_after
                    }
                )
                response.headers["X-RateLimit-Limit"] = str(e.limit)
                response.headers["X-RateLimit-Remaining"] = "0"
                response.headers["Retry-After"] = str(e.retry_after)

                reset_key = RateLimiter._get_reset_key(endpoint, client_id)
                reset_time = cache.redis_client.get(reset_key)
                if reset_time:
                    response.headers["X-RateLimit-Reset"] = str(reset_time)

                return response

        return wrapper

    return decorator


def rate_limit_factory(
    config_attr: str,
    endpoint_name: Optional[str] = None
) -> Callable:
    """
    Factory function for creating rate limit decorators from config.

    Uses configuration from settings module to dynamically set rate limits.

    Args:
        config_attr: Name of the config attribute (e.g., 'RATE_LIMIT_UNIFIED_OVERVIEW')
        endpoint_name: Optional custom endpoint name for Redis key

    Returns:
        Configured rate limit decorator

    Example:
        @rate_limit_factory('RATE_LIMIT_UNIFIED_OVERVIEW')
        async def get_unified_overview(db: AsyncSession):
            ...
    """
    # Get limit from config with fallback
    limit = getattr(settings, config_attr.lower(), 100)
    window = getattr(settings, 'rate_limit_window', 60)

    return rate_limit(requests=limit, window_seconds=window, endpoint_name=endpoint_name)
