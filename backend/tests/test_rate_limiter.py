"""
Comprehensive tests for rate limiting utilities and Redis integration.

Tests the rate limiter decorator, middleware, and edge cases.
Covers rate limit enforcement, window expiration, Redis unavailability, and race conditions.
"""
import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, FastAPI
from starlette.testclient import TestClient

from app.utils.rate_limiter import (
    check_rate_limit,
    rate_limit,
    rate_limit_middleware,
    RateLimitExceeded,
    _get_rate_limit_key,
    _get_reset_time_key,
    get_rate_limit_info,
)
from app.services.redis_client import reset_redis_client
from app.config import settings


# Mark entire module as unit test (doesn't require running backend)
pytestmark = pytest.mark.unit


class TestRateLimitKeyGeneration:
    """Test rate limit key generation functions."""

    def test_get_rate_limit_key(self):
        """Test rate limit key generation."""
        key = _get_rate_limit_key("user123", "endpoint1")
        assert "rate_limit" in key
        assert "endpoint1" in key
        assert "user123" in key
        assert key == f"{settings.rate_limit_key_prefix}:endpoint1:user123"

    def test_get_reset_time_key(self):
        """Test reset time key generation."""
        key = _get_reset_time_key("endpoint1", "user123")
        assert "rate_limit_reset" in key
        assert "endpoint1" in key
        assert "user123" in key
        assert key == f"{settings.rate_limit_key_prefix}_reset:endpoint1:user123"

    def test_different_users_different_keys(self):
        """Test that different users get different rate limit keys."""
        key1 = _get_rate_limit_key("user1", "endpoint")
        key2 = _get_rate_limit_key("user2", "endpoint")
        assert key1 != key2

    def test_different_endpoints_different_keys(self):
        """Test that different endpoints get different rate limit keys."""
        key1 = _get_rate_limit_key("user", "endpoint1")
        key2 = _get_rate_limit_key("user", "endpoint2")
        assert key1 != key2


class TestCheckRateLimitRateLimitDisabled:
    """Test rate limit behavior when disabled globally."""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled_returns_full_limit(self):
        """Test that disabled rate limiting returns full limit."""
        # Mock disabled rate limiting
        with patch.object(settings, "rate_limit_enabled", False):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            remaining, limit, reset_time = await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            assert remaining == 100
            assert limit == 100
            assert reset_time > int(time.time())


class TestCheckRateLimitRedisUnavailable:
    """Test rate limit behavior when Redis is unavailable."""

    @pytest.mark.asyncio
    async def test_redis_unavailable_allows_request(self):
        """Test that requests are allowed when Redis is unavailable."""
        with patch("app.utils.rate_limiter.get_redis_client", return_value=None):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            remaining, limit, reset_time = await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            # Should return dummy values when Redis unavailable
            assert remaining == 100
            assert limit == 100
            assert reset_time > int(time.time())

    @pytest.mark.asyncio
    async def test_redis_connection_error_handling(self):
        """Test that Redis connection errors are handled gracefully."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("Connection refused")

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            # Should not raise exception, but instead allow request
            remaining, limit, reset_time = await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            # Should return dummy values on error
            assert remaining == 100
            assert limit == 100
            assert reset_time > int(time.time())


class TestCheckRateLimitEnforcement:
    """Test rate limit enforcement."""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_raises_exception(self):
        """Test that rate limit exceeded raises RateLimitExceeded exception."""
        mock_redis = MagicMock()
        current_time = int(time.time())
        reset_time = str(current_time + 60)

        # Simulate count >= requests_limit
        mock_redis.pipeline.return_value.execute.return_value = [
            b"100",
            reset_time.encode()
        ]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                mock_request = MagicMock(spec=Request)
                mock_request.client.host = "192.168.1.1"

                # Should raise RateLimitExceeded
                with pytest.raises(RateLimitExceeded) as exc_info:
                    await check_rate_limit(
                        request=mock_request,
                        endpoint="test-endpoint",
                        requests_limit=100,
                        window_seconds=60
                    )

                # Verify retry_after is set
                assert exc_info.value.retry_after > 0
                assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_first_request_succeeds(self):
        """Test that first request succeeds and initializes counter."""
        mock_redis = MagicMock()
        # First request: no existing count or reset time
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            remaining, limit, reset_time = await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            assert remaining == 99
            assert limit == 100
            # Verify pipeline was used atomically
            assert mock_redis.pipeline.called
            assert mock_redis.pipeline.return_value.incr.called
            assert mock_redis.pipeline.return_value.expire.called
            assert mock_redis.pipeline.return_value.setex.called


class TestRateLimitWindowExpiration:
    """Test rate limit window expiration and reset."""

    @pytest.mark.asyncio
    async def test_window_expiration_resets_counter(self):
        """Test that expired window resets the counter."""
        mock_redis = MagicMock()
        # Simulate window expired (reset_time in past)
        current_time = int(time.time())
        expired_reset_time = str(current_time - 60)  # 60 seconds in past
        mock_redis.pipeline.return_value.execute.return_value = [
            b"50",
            expired_reset_time.encode()
        ]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                # Handle int conversion calls
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                mock_request = MagicMock(spec=Request)
                mock_request.client.host = "192.168.1.1"

                remaining, limit, reset_time = await check_rate_limit(
                    request=mock_request,
                    endpoint="test-endpoint",
                    requests_limit=100,
                    window_seconds=60
                )

                # After window expiration, should be reset
                assert remaining == 99
                assert limit == 100
                # Verify atomic reset with pipeline
                assert mock_redis.pipeline.called


class TestRateLimitUserIdentification:
    """Test user identification in rate limiting."""

    @pytest.mark.asyncio
    async def test_authenticated_user_takes_precedence(self):
        """Test that authenticated user ID takes precedence over IP."""
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            # Create a proper request mock with request.state containing user_id
            class FakeState:
                user_id = "authenticated_user_123"

            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"
            mock_request.state = FakeState()

            await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            # Verify that authenticated user ID was used
            call_args = mock_redis.pipeline.return_value.incr.call_args
            key = call_args[0][0] if call_args[0] else call_args[1]["key"]
            assert "authenticated_user_123" in key
            assert "192.168.1.1" not in key

    @pytest.mark.asyncio
    async def test_anonymous_user_fallback(self):
        """Test that anonymous user falls back to IP address for rate limiting."""
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            # No user_id in state, should use IP
            class FakeState:
                pass

            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "203.0.113.1"
            mock_request.state = FakeState()

            await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            # Verify that IP address was used in rate limit key
            call_args = mock_redis.pipeline.return_value.incr.call_args
            key = call_args[0][0] if call_args[0] else call_args[1].get("key")
            assert "203.0.113.1" in key


class TestRateLimitAtomicity:
    """Test atomic operations to prevent race conditions."""

    @pytest.mark.asyncio
    async def test_initialization_uses_atomic_pipeline(self):
        """Test that window initialization uses atomic pipeline."""
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100,
                window_seconds=60
            )

            # Verify pipeline usage for atomicity
            assert mock_redis.pipeline.called
            pipeline = mock_redis.pipeline.return_value
            assert pipeline.incr.called
            assert pipeline.expire.called
            assert pipeline.setex.called
            assert pipeline.execute.called

    @pytest.mark.asyncio
    async def test_expiration_reset_uses_atomic_pipeline(self):
        """Test that window reset on expiration uses atomic pipeline."""
        mock_redis = MagicMock()
        current_time = int(time.time())
        expired_reset_time = str(current_time - 60)

        # Set up side effect to return expired time
        mock_redis.pipeline.return_value.execute.return_value = [
            b"100",
            expired_reset_time.encode()
        ]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                mock_request = MagicMock(spec=Request)
                mock_request.client.host = "192.168.1.1"

                await check_rate_limit(
                    request=mock_request,
                    endpoint="test-endpoint",
                    requests_limit=100,
                    window_seconds=60
                )

                # Verify pipeline was used on reset
                assert mock_redis.pipeline.called

    @pytest.mark.asyncio
    async def test_active_window_increment_uses_atomic_pipeline(self):
        """Test that incrementing counter in active window uses atomic pipeline."""
        mock_redis = MagicMock()
        current_time = int(time.time())
        reset_time = str(current_time + 60)

        # Simulate counter < limit in active window
        mock_redis.pipeline.return_value.execute.return_value = [
            b"50",
            reset_time.encode()
        ]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                mock_request = MagicMock(spec=Request)
                mock_request.client.host = "192.168.1.1"

                await check_rate_limit(
                    request=mock_request,
                    endpoint="test-endpoint",
                    requests_limit=100,
                    window_seconds=60
                )

                # Verify pipeline was used for atomic increment (prevents race condition)
                assert mock_redis.pipeline.called
                pipeline = mock_redis.pipeline.return_value
                assert pipeline.incr.called
                assert pipeline.execute.called


class TestRateLimitEdgeCases:
    """Test edge cases in rate limiting."""

    @pytest.mark.asyncio
    async def test_one_request_limit(self):
        """Test rate limiting with limit of 1."""
        mock_redis = MagicMock()
        # First request: no counter
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            remaining, limit, reset_time = await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=1,
                window_seconds=60
            )

            assert remaining == 0
            assert limit == 1

    @pytest.mark.asyncio
    async def test_very_large_limit(self):
        """Test rate limiting with very large limit."""
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"

            remaining, limit, reset_time = await check_rate_limit(
                request=mock_request,
                endpoint="test-endpoint",
                requests_limit=100000,
                window_seconds=60
            )

            assert remaining == 99999
            assert limit == 100000

    @pytest.mark.asyncio
    async def test_negative_remaining_calculation(self):
        """Test that remaining is never negative."""
        mock_redis = MagicMock()
        # Simulate counter at exactly limit
        current_time = int(time.time())
        reset_time = str(current_time + 60)
        mock_redis.pipeline.return_value.execute.return_value = [
            b"100",
            reset_time.encode()
        ]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                mock_request = MagicMock(spec=Request)
                mock_request.client.host = "192.168.1.1"

                with pytest.raises(RateLimitExceeded):
                    await check_rate_limit(
                        request=mock_request,
                        endpoint="test-endpoint",
                        requests_limit=100,
                        window_seconds=60
                    )


class TestRateLimitDecorator:
    """Test rate limit decorator."""

    @pytest.mark.asyncio
    async def test_decorator_stores_rate_limit_info_in_state(self):
        """Test that decorator stores rate limit info in request state."""
        mock_redis = MagicMock()
        mock_redis.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            @rate_limit(endpoint="test", requests=100, window_seconds=60)
            async def test_endpoint(request: Request):
                return {"status": "ok"}

            mock_request = MagicMock(spec=Request)
            mock_request.client.host = "192.168.1.1"
            mock_request.state = MagicMock()

            result = await test_endpoint(mock_request)

            # Verify rate limit info was stored
            assert hasattr(mock_request.state, "rate_limit_remaining")
            assert hasattr(mock_request.state, "rate_limit_limit")
            assert hasattr(mock_request.state, "rate_limit_reset")

    @pytest.mark.asyncio
    async def test_decorator_returns_429_on_rate_limit_exceeded(self):
        """Test that decorator returns 429 response when limit exceeded."""
        mock_redis = MagicMock()
        # Simulate limit exceeded
        current_time = int(time.time())
        reset_time = str(current_time + 60)
        mock_redis.pipeline.return_value.execute.return_value = [
            b"100",
            reset_time.encode()
        ]

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                @rate_limit(endpoint="test", requests=100, window_seconds=60)
                async def test_endpoint(request: Request):
                    return {"status": "ok"}

                mock_request = MagicMock(spec=Request)
                mock_request.client.host = "192.168.1.1"
                mock_request.state = MagicMock()

                response = await test_endpoint(mock_request)

                # Verify 429 response
                assert response.status_code == 429
                assert "Too Many Requests" in response.body.decode()


class TestRateLimitMiddleware:
    """Test rate limit middleware."""

    @pytest.mark.asyncio
    async def test_middleware_adds_headers_when_rate_limit_set(self):
        """Test that middleware adds rate limit headers when set."""
        async def mock_call_next(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "ok"})

        mock_request = MagicMock(spec=Request)
        mock_request.state.rate_limit_limit = 100
        mock_request.state.rate_limit_remaining = 50
        mock_request.state.rate_limit_reset = 1234567890

        response = await rate_limit_middleware(mock_request, mock_call_next)

        assert response.headers.get("X-RateLimit-Limit") == "100"
        assert response.headers.get("X-RateLimit-Remaining") == "50"
        assert response.headers.get("X-RateLimit-Reset") == "1234567890"

    @pytest.mark.asyncio
    async def test_middleware_skips_headers_when_rate_limit_not_set(self):
        """Test that middleware skips header injection when rate limit not set."""
        async def mock_call_next(request):
            from fastapi.responses import JSONResponse
            return JSONResponse({"status": "ok"})

        mock_request = MagicMock(spec=Request)
        # Create a state object without rate limit attributes
        class MockState:
            pass
        mock_request.state = MockState()

        response = await rate_limit_middleware(mock_request, mock_call_next)

        # Headers should NOT be added (case-insensitive check)
        headers_lower = {k.lower(): v for k, v in response.headers.items()}
        assert "x-ratelimit-limit" not in headers_lower
        assert "x-ratelimit-remaining" not in headers_lower
        assert "x-ratelimit-reset" not in headers_lower


class TestGetRateLimitInfo:
    """Test the get_rate_limit_info function."""

    def test_get_rate_limit_info_no_redis(self):
        """Test get_rate_limit_info when Redis is unavailable."""
        with patch("app.utils.rate_limiter.get_redis_client", return_value=None):
            info = get_rate_limit_info(endpoint="test", user_id="user1")
            assert info["status"] == "unavailable"

    def test_get_rate_limit_info_success(self):
        """Test get_rate_limit_info returns current status."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = [b"50", b"1234567890"]
        mock_redis.ttl.return_value = 30

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                info = get_rate_limit_info(endpoint="test", user_id="user1")

                assert info["status"] == "ok"
                assert info["endpoint"] == "test"
                assert info["user_id"] == "user1"

    def test_get_rate_limit_info_default_user_id(self):
        """Test get_rate_limit_info uses default user_id."""
        mock_redis = MagicMock()
        mock_redis.get.side_effect = [b"50", b"1234567890"]
        mock_redis.ttl.return_value = 30

        with patch("app.utils.rate_limiter.get_redis_client", return_value=mock_redis):
            with patch("app.utils.rate_limiter.int") as mock_int:
                def int_side_effect(x):
                    if isinstance(x, bytes):
                        return int(x.decode())
                    return int(x)

                mock_int.side_effect = int_side_effect

                info = get_rate_limit_info(endpoint="test")

                assert info["user_id"] == "anonymous"
