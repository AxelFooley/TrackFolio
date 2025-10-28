"""
Rate limiting utilities for FastAPI endpoints.

Implements a sliding window rate limiter using Redis as the backend.
Provides decorators to limit request rates on FastAPI routes.

Rate limit info is stored per request in state for use by middleware or inline headers.
"""
import functools
import logging
import time
from typing import Callable, Optional, Any, Awaitable, Tuple
from fastapi import HTTPException, Request

from app.config import settings
from app.services.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, retry_after: int):
        """
        Initialize rate limit exceeded exception.

        Args:
            retry_after: Seconds to wait before retrying
        """
        super().__init__(
            status_code=429,
            detail="Too Many Requests"
        )
        self.retry_after = retry_after


def _get_rate_limit_key(user_id: str, endpoint: str) -> str:
    """
    Generate a rate limit key for Redis.

    Args:
        user_id: User identifier (or "anonymous" for unauthenticated requests)
        endpoint: API endpoint identifier

    Returns:
        Redis key string
    """
    prefix = settings.rate_limit_key_prefix
    return f"{prefix}:{endpoint}:{user_id}"


def _get_reset_time_key(endpoint: str, user_id: str) -> str:
    """
    Generate a key to store reset time for the rate limit window.

    Args:
        endpoint: API endpoint identifier
        user_id: User identifier

    Returns:
        Redis key string
    """
    prefix = settings.rate_limit_key_prefix
    return f"{prefix}_reset:{endpoint}:{user_id}"


async def check_rate_limit(
    request: Request,
    endpoint: str,
    requests_limit: int,
    window_seconds: int
) -> Tuple[int, int, int]:
    """
    Check if a request is within the rate limit.

    Args:
        request: FastAPI Request object
        endpoint: API endpoint identifier for the rate limit bucket
        requests_limit: Maximum requests allowed in the window
        window_seconds: Time window in seconds

    Returns:
        Tuple of (remaining_requests, limit, reset_time_unix)

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    # Check if rate limiting is enabled globally
    if not settings.rate_limit_enabled:
        reset_time = int(time.time()) + window_seconds
        return (requests_limit, requests_limit, reset_time)

    # Prefer authenticated user ID, fallback to IP address
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        user_id = request.client.host if request.client else "anonymous"

    redis_client = get_redis_client()

    # If Redis is unavailable, allow request but log warning
    if redis_client is None:
        logger.warning(f"Redis unavailable for rate limiting on endpoint {endpoint}")
        # Return dummy values (no limit enforced)
        reset_time = int(time.time()) + window_seconds
        return (requests_limit, requests_limit, reset_time)

    try:
        rate_limit_key = _get_rate_limit_key(user_id, endpoint)
        reset_time_key = _get_reset_time_key(endpoint, user_id)

        # Use Redis pipeline to fetch both keys in one call (optimization)
        pipe = redis_client.pipeline()
        pipe.get(rate_limit_key)
        pipe.get(reset_time_key)
        results = pipe.execute()
        current_count = results[0]
        reset_time = results[1]

        current_time = int(time.time())

        # Initialize or check reset
        if current_count is None or reset_time is None:
            # First request in window or window expired
            # Use atomic pipeline to prevent race condition where multiple requests
            # both see None and both initialize to 1 (INCR + EXPIRE + SETEX must be atomic)
            reset_time_unix = current_time + window_seconds
            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, window_seconds)
            pipe.setex(reset_time_key, window_seconds, str(reset_time_unix))
            pipe.execute()
            logger.debug(f"Rate limit window reset for {endpoint} user {user_id}")
            remaining = requests_limit - 1
            limit = requests_limit
            return (remaining, limit, reset_time_unix)

        reset_time_unix = int(reset_time)

        # Check if window has expired
        if current_time >= reset_time_unix:
            # Window expired, reset counter using atomic pipeline
            reset_time_unix = current_time + window_seconds
            pipe = redis_client.pipeline()
            pipe.incr(rate_limit_key)
            pipe.expire(rate_limit_key, window_seconds)
            pipe.setex(reset_time_key, window_seconds, str(reset_time_unix))
            pipe.execute()
            logger.debug(f"Rate limit window reset for {endpoint} user {user_id}")
            remaining = requests_limit - 1
            limit = requests_limit
            return (remaining, limit, reset_time_unix)

        # Window still active
        count = int(current_count)

        if count >= requests_limit:
            # Rate limit exceeded
            retry_after = reset_time_unix - current_time
            logger.warning(
                f"Rate limit exceeded for {endpoint} (user: {user_id}, "
                f"count: {count}, limit: {requests_limit}, retry_after: {retry_after}s)"
            )
            raise RateLimitExceeded(retry_after=retry_after)

        # Increment counter
        redis_client.incr(rate_limit_key)
        remaining = requests_limit - (count + 1)
        limit = requests_limit

        logger.debug(
            f"Rate limit check passed for {endpoint} (user: {user_id}, "
            f"remaining: {remaining}, limit: {limit})"
        )

        return (remaining, limit, reset_time_unix)

    except RateLimitExceeded:
        raise
    except Exception as e:
        logger.error(f"Error checking rate limit for {endpoint}: {e}")
        # On error, allow request but log it
        reset_time = int(time.time()) + window_seconds
        return (requests_limit, requests_limit, reset_time)


def rate_limit(
    endpoint: str,
    requests: int = 100,
    window_seconds: int = 60
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """
    Decorator to apply rate limiting to a FastAPI endpoint.

    Usage:
        @router.get("/expensive-endpoint")
        @rate_limit(endpoint="expensive-endpoint", requests=50, window_seconds=60)
        async def expensive_endpoint(request: Request, db: AsyncSession = Depends(get_db)):
            ...

    Args:
        endpoint: Unique identifier for the rate limit bucket
        requests: Maximum number of requests allowed in the window
        window_seconds: Time window in seconds

    Returns:
        Decorated function that enforces rate limiting

    Note:
        The decorated function must have a 'request: Request' parameter.
        Rate limit info is stored in request.state for middleware to add headers.
        Header injection is handled by the rate_limit_middleware for all responses.
    """
    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(func)
        async def async_wrapper(request: Request, *args, **kwargs):
            # Check rate limit
            remaining = requests
            limit = requests
            reset_time = int(time.time()) + window_seconds

            try:
                remaining, limit, reset_time = await check_rate_limit(
                    request=request,
                    endpoint=endpoint,
                    requests_limit=requests,
                    window_seconds=window_seconds
                )

                # Store rate limit info in request state for middleware
                request.state.rate_limit_remaining = remaining
                request.state.rate_limit_limit = limit
                request.state.rate_limit_reset = reset_time

            except RateLimitExceeded as e:
                # Return 429 response with proper headers for rate limit exceeded
                from fastapi.responses import JSONResponse

                return JSONResponse(
                    status_code=429,
                    content={
                        "status": "error",
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Please try again later.",
                        "retry_after": e.retry_after
                    },
                    headers={
                        "Retry-After": str(e.retry_after),
                        "X-RateLimit-Limit": str(requests),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_time)
                    }
                )

            # Call the original function
            response = await func(request, *args, **kwargs)

            return response

        return async_wrapper

    return decorator


async def rate_limit_middleware(request: Request, call_next):
    """
    Middleware to add rate limit headers to responses.

    Should be added to FastAPI app:
        app.middleware("http")(rate_limit_middleware)

    Reads rate limit info from request.state and adds it to response headers.
    """
    response = await call_next(request)

    # Add rate limit headers if they were set by the decorator
    if hasattr(request.state, "rate_limit_limit"):
        response.headers["X-RateLimit-Limit"] = str(request.state.rate_limit_limit)
        response.headers["X-RateLimit-Remaining"] = str(request.state.rate_limit_remaining)
        response.headers["X-RateLimit-Reset"] = str(request.state.rate_limit_reset)

    return response


def get_rate_limit_info(endpoint: str, user_id: str = None) -> dict:
    """
    Get current rate limit information for a user and endpoint.

    Useful for debugging and monitoring.

    Args:
        endpoint: API endpoint identifier
        user_id: User identifier (defaults to "anonymous")

    Returns:
        Dictionary with rate limit status
    """
    if user_id is None:
        user_id = "anonymous"

    redis_client = get_redis_client()

    if redis_client is None:
        return {
            "status": "unavailable",
            "message": "Redis not available"
        }

    try:
        rate_limit_key = _get_rate_limit_key(user_id, endpoint)
        reset_time_key = _get_reset_time_key(endpoint, user_id)

        current_count = redis_client.get(rate_limit_key)
        reset_time = redis_client.get(reset_time_key)
        ttl = redis_client.ttl(rate_limit_key)

        current_time = int(time.time())

        return {
            "status": "ok",
            "endpoint": endpoint,
            "user_id": user_id,
            "current_count": int(current_count) if current_count else 0,
            "reset_time": int(reset_time) if reset_time else None,
            "seconds_until_reset": max(0, int(reset_time) - current_time) if reset_time else None,
            "ttl_seconds": ttl
        }
    except Exception as e:
        logger.error(f"Error getting rate limit info: {e}")
        return {
            "status": "error",
            "message": str(e)
        }
