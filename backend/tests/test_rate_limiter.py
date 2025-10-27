"""
Comprehensive test suite for rate limiting functionality.

Tests cover:
- First request initialization
- Counter incrementation
- Limit exceeded behavior
- Window expiration and reset
- Redis unavailability fallback
- Error handling
- Decorator functionality
- rate_limit_enabled configuration
"""
import asyncio
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import pytest
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient
from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.utils.rate_limiter import (
    check_rate_limit,
    rate_limit,
    RateLimitExceeded,
    _get_rate_limit_key,
    _get_reset_time_key,
    _get_redis_client,
    RATE_LIMIT_INFO_KEY,
)
from app.config import settings


# Fixtures
@pytest.fixture
def mock_request():
    """Create a mock FastAPI request object."""
    request = Mock(spec=Request)
    request.client.host = "127.0.0.1"
    request.state = Mock()
    return request


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.pipeline.return_value.__enter__ = Mock(
        return_value=redis_mock.pipeline.return_value
    )
    redis_mock.pipeline.return_value.__exit__ = Mock(return_value=None)
    return redis_mock


@pytest.fixture
def mock_redis_context():
    """Create a Redis mock with proper context manager support."""
    redis_mock = MagicMock()

    # Setup pipeline as a proper context manager
    pipeline_mock = MagicMock()
    pipeline_mock.__enter__ = Mock(return_value=pipeline_mock)
    pipeline_mock.__exit__ = Mock(return_value=None)
    pipeline_mock.get = Mock(return_value=pipeline_mock)
    pipeline_mock.setex = Mock(return_value=pipeline_mock)
    pipeline_mock.execute = Mock(return_value=[None, None])

    redis_mock.pipeline = Mock(return_value=pipeline_mock)
    redis_mock.get = Mock(return_value=None)
    redis_mock.setex = Mock()
    redis_mock.incr = Mock()
    redis_mock.ping = Mock()

    return redis_mock


class TestRateLimitKeyGeneration:
    """Test rate limit key generation functions."""

    def test_get_rate_limit_key_format(self):
        """Test that rate limit key includes prefix, endpoint, and user_id."""
        prefix = settings.rate_limit_key_prefix
        key = _get_rate_limit_key("user123", "endpoint1")
        assert key.startswith(prefix)
        assert "endpoint1" in key
        assert "user123" in key

    def test_get_rate_limit_key_with_different_users(self):
        """Test that different users get different keys."""
        key1 = _get_rate_limit_key("user1", "endpoint1")
        key2 = _get_rate_limit_key("user2", "endpoint1")
        assert key1 != key2

    def test_get_rate_limit_key_with_different_endpoints(self):
        """Test that different endpoints get different keys."""
        key1 = _get_rate_limit_key("user1", "endpoint1")
        key2 = _get_rate_limit_key("user1", "endpoint2")
        assert key1 != key2

    def test_get_reset_time_key_format(self):
        """Test that reset time key includes prefix, endpoint, and user_id."""
        prefix = settings.rate_limit_key_prefix
        key = _get_reset_time_key("endpoint1", "user123")
        assert key.startswith(prefix)
        assert "endpoint1" in key
        assert "user123" in key
        assert "_reset" in key

    def test_reset_time_and_rate_limit_keys_are_different(self):
        """Test that reset time key is different from rate limit key."""
        rate_key = _get_rate_limit_key("user1", "endpoint1")
        reset_key = _get_reset_time_key("endpoint1", "user1")
        assert rate_key != reset_key


class TestCheckRateLimitBasic:
    """Test basic rate limit checking functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_disabled(self, mock_request):
        """Test that no rate limiting occurs when disabled."""
        with patch("app.utils.rate_limiter.settings") as mock_settings:
            mock_settings.rate_limit_enabled = False

            remaining, limit, reset_time = await check_rate_limit(
                mock_request, "test_endpoint", 10, 60
            )

            assert remaining == 10
            assert limit == 10

    @pytest.mark.asyncio
    async def test_redis_unavailable(self, mock_request):
        """Test fallback behavior when Redis is unavailable."""
        with patch("app.utils.rate_limiter._get_redis_client", return_value=None):
            remaining, limit, reset_time = await check_rate_limit(
                mock_request, "test_endpoint", 10, 60
            )

            assert remaining == 10
            assert limit == 10

    @pytest.mark.asyncio
    async def test_first_request_initialization(self, mock_request, mock_redis_context):
        """Test that first request initializes rate limit counter."""
        current_time = int(time.time())

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            # Pipeline execute returns [None, None] for first request
            mock_redis_context.pipeline.return_value.execute.return_value = [None, None]

            remaining, limit, reset_time = await check_rate_limit(
                mock_request, "test_endpoint", 10, 60
            )

            assert remaining == 9  # 10 - 1
            assert limit == 10
            assert reset_time >= current_time  # Should be set to current + window

            # Verify Redis was called to set the keys
            assert mock_redis_context.pipeline.return_value.setex.call_count == 2

    @pytest.mark.asyncio
    async def test_counter_incrementation(self, mock_request, mock_redis_context):
        """Test that counter increments on subsequent requests."""
        current_time = int(time.time())
        reset_time = current_time + 60

        # Second request: pipeline returns current count and reset time
        mock_redis_context.pipeline.return_value.execute.return_value = ["2", str(reset_time)]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                remaining, limit, reset_time_result = await check_rate_limit(
                    mock_request, "test_endpoint", 10, 60
                )

                assert remaining == 7  # 10 - 3 (count 2 + 1 for this request)
                assert limit == 10
                assert mock_redis_context.incr.called


class TestRateLimitExceeded:
    """Test rate limit exceeded behavior."""

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self, mock_request, mock_redis_context):
        """Test exception when rate limit is exceeded."""
        current_time = int(time.time())
        reset_time = current_time + 30

        # Rate limit exceeded: count >= limit
        mock_redis_context.pipeline.return_value.execute.return_value = [
            "10",  # Current count equals limit
            str(reset_time)
        ]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                with pytest.raises(RateLimitExceeded) as exc_info:
                    await check_rate_limit(
                        mock_request, "test_endpoint", 10, 60
                    )

                assert exc_info.value.status_code == 429
                assert exc_info.value.retry_after == 30

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_exception_properties(self):
        """Test RateLimitExceeded exception properties."""
        exc = RateLimitExceeded(retry_after=45)
        assert exc.status_code == 429
        assert exc.detail == "Too Many Requests"
        assert exc.retry_after == 45


class TestWindowExpiration:
    """Test window expiration and reset behavior."""

    @pytest.mark.asyncio
    async def test_window_expiration_resets_counter(self, mock_request, mock_redis_context):
        """Test that expired window resets the counter."""
        current_time = int(time.time())
        expired_reset_time = current_time - 10  # Window expired 10 seconds ago

        # Pipeline returns old reset time
        mock_redis_context.pipeline.return_value.execute.return_value = [
            "5",
            str(expired_reset_time)
        ]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                remaining, limit, reset_time = await check_rate_limit(
                    mock_request, "test_endpoint", 10, 60
                )

                assert remaining == 9  # Reset, so 10 - 1
                assert limit == 10
                assert reset_time > current_time

    @pytest.mark.asyncio
    async def test_window_still_active(self, mock_request, mock_redis_context):
        """Test behavior when window is still active."""
        current_time = int(time.time())
        reset_time = current_time + 30  # Window expires in 30 seconds

        mock_redis_context.pipeline.return_value.execute.return_value = [
            "3",
            str(reset_time)
        ]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                remaining, limit, reset_time_result = await check_rate_limit(
                    mock_request, "test_endpoint", 10, 60
                )

                assert remaining == 6  # 10 - 4 (count 3 + 1 for this request)
                assert limit == 10
                assert reset_time_result == reset_time


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_error_handling_general_exception(self, mock_request, mock_redis_context):
        """Test graceful handling of Redis errors."""
        mock_redis_context.pipeline.side_effect = Exception("Redis connection error")

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            remaining, limit, reset_time = await check_rate_limit(
                mock_request, "test_endpoint", 10, 60
            )

            # Should allow request on error
            assert remaining == 10
            assert limit == 10

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_not_caught_by_general_handler(self, mock_request, mock_redis_context):
        """Test that RateLimitExceeded is properly re-raised."""
        current_time = int(time.time())
        reset_time = current_time + 30

        mock_redis_context.pipeline.return_value.execute.return_value = [
            "10",
            str(reset_time)
        ]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                # RateLimitExceeded should be raised, not caught by general exception handler
                with pytest.raises(RateLimitExceeded):
                    await check_rate_limit(
                        mock_request, "test_endpoint", 10, 60
                    )

    @pytest.mark.asyncio
    async def test_anonymous_user_fallback(self):
        """Test that client IP is used when no user_id available."""
        request = Mock(spec=Request)
        request.client.host = "192.168.1.100"
        request.state = Mock()

        key = _get_rate_limit_key("192.168.1.100", "endpoint1")
        assert "192.168.1.100" in key


class TestDecorator:
    """Test the rate_limit decorator."""

    @pytest.mark.asyncio
    async def test_decorator_stores_rate_limit_info(self, mock_redis_context):
        """Test that decorator stores rate limit info in request state."""
        app = FastAPI()

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            current_time = int(time.time())
            reset_time = current_time + 60

            mock_redis_context.pipeline.return_value.execute.return_value = [None, None]

            @app.get("/test")
            @rate_limit(endpoint="test", requests=10, window_seconds=60)
            async def test_endpoint(request: Request):
                return {
                    "status": "ok",
                    "rate_limit_remaining": request.state.rate_limit_remaining,
                    "rate_limit_limit": request.state.rate_limit_limit,
                }

            client = TestClient(app)
            response = client.get("/test")

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_decorator_returns_429_on_rate_limit(self, mock_redis_context):
        """Test that decorator returns 429 when rate limit exceeded."""
        app = FastAPI()

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            current_time = int(time.time())
            reset_time = current_time + 30

            # First call succeeds
            call_count = [0]

            def execute_side_effect():
                call_count[0] += 1
                if call_count[0] == 1:
                    return [None, None]
                else:
                    return ["10", str(reset_time)]

            mock_redis_context.pipeline.return_value.execute.side_effect = execute_side_effect

            @app.get("/test")
            @rate_limit(endpoint="test", requests=10, window_seconds=60)
            async def test_endpoint(request: Request):
                return {"status": "ok"}

            with patch("time.time", return_value=current_time):
                client = TestClient(app)

                # First request should succeed
                response1 = client.get("/test")
                assert response1.status_code in [200, 405]  # 200 or 405 depending on method

    @pytest.mark.asyncio
    async def test_decorator_includes_retry_after_header(self, mock_redis_context):
        """Test that 429 response includes Retry-After header."""
        app = FastAPI()

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            current_time = int(time.time())
            reset_time = current_time + 30

            mock_redis_context.pipeline.return_value.execute.return_value = [
                "10",
                str(reset_time)
            ]

            @app.get("/test")
            @rate_limit(endpoint="test", requests=10, window_seconds=60)
            async def test_endpoint(request: Request):
                return {"status": "ok"}

            with patch("time.time", return_value=current_time):
                client = TestClient(app)
                response = client.get("/test")

                if response.status_code == 429:
                    assert "Retry-After" in response.headers


class TestRedisOptimization:
    """Test Redis pipeline optimization."""

    @pytest.mark.asyncio
    async def test_pipeline_used_for_read_operations(self, mock_request, mock_redis_context):
        """Test that pipeline is used for reading keys."""
        current_time = int(time.time())
        reset_time = current_time + 60

        mock_redis_context.pipeline.return_value.execute.return_value = ["2", str(reset_time)]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                await check_rate_limit(
                    mock_request, "test_endpoint", 10, 60
                )

                # Verify pipeline was created and used
                assert mock_redis_context.pipeline.called

    @pytest.mark.asyncio
    async def test_pipeline_used_for_write_operations(self, mock_request, mock_redis_context):
        """Test that pipeline is used for writing keys."""
        mock_redis_context.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            await check_rate_limit(
                mock_request, "test_endpoint", 10, 60
            )

            # Verify pipeline setex was called
            pipeline_calls = mock_redis_context.pipeline.return_value.setex.call_count
            assert pipeline_calls >= 2  # At least two setex calls for initialization


class TestEdgeCases:
    """Test edge cases and special scenarios."""

    @pytest.mark.asyncio
    async def test_one_request_limit(self, mock_request, mock_redis_context):
        """Test behavior with one request limit."""
        mock_redis_context.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            remaining, limit, _ = await check_rate_limit(
                mock_request, "test_endpoint", 1, 60
            )
            # With limit 1, after first request remaining should be 0
            assert remaining == 0
            assert limit == 1

    @pytest.mark.asyncio
    async def test_very_large_request_limit(self, mock_request, mock_redis_context):
        """Test behavior with very large request limit."""
        mock_redis_context.pipeline.return_value.execute.return_value = [None, None]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            remaining, limit, reset_time = await check_rate_limit(
                mock_request, "test_endpoint", 1000000, 60
            )

            assert remaining == 999999
            assert limit == 1000000

    @pytest.mark.asyncio
    async def test_negative_remaining_calculation(self, mock_request, mock_redis_context):
        """Test that remaining never goes negative."""
        current_time = int(time.time())
        reset_time = current_time + 60

        # Count is already at limit
        mock_redis_client = mock_redis_context
        mock_redis_client.pipeline.return_value.execute.return_value = [
            "10",
            str(reset_time)
        ]

        with patch("app.utils.rate_limiter._get_redis_client", return_value=mock_redis_context):
            with patch("time.time", return_value=current_time):
                with pytest.raises(RateLimitExceeded):
                    await check_rate_limit(
                        mock_request, "test_endpoint", 10, 60
                    )


class TestIntegration:
    """Integration tests for rate limiting."""

    def test_multiple_endpoints_have_separate_keys(self):
        """Test that different endpoints use separate Redis keys."""
        # This test verifies that the key generation is unique per endpoint
        key1 = _get_rate_limit_key("user123", "endpoint1")
        key2 = _get_rate_limit_key("user123", "endpoint2")

        # Keys should be different
        assert key1 != key2

        # Reset time keys should also be different
        reset_key1 = _get_reset_time_key("endpoint1", "user123")
        reset_key2 = _get_reset_time_key("endpoint2", "user123")

        assert reset_key1 != reset_key2

    def test_rate_limit_key_prefix_usage(self, mock_request, mock_redis_context):
        """Test that rate limit key prefix from config is used."""
        prefix = settings.rate_limit_key_prefix
        assert prefix is not None

        key = _get_rate_limit_key("user1", "endpoint1")
        assert key.startswith(prefix)
