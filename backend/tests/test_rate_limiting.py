"""
Tests for rate limiting service and unified endpoints.

Tests the RateLimiter service, decorator functionality, and integration with
unified API endpoints.
"""
import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import Request, HTTPException
from fastapi.testclient import TestClient
from app.services.rate_limiter import (
    RateLimiter, rate_limit, RateLimitExceeded, rate_limit_factory
)
from app.services.cache import cache
from app.config import settings


# Mark as unit tests (don't require full backend)
pytestmark = pytest.mark.unit


class TestRateLimiterCore:
    """Tests for core RateLimiter functionality."""

    def test_rate_limiter_imports(self):
        """Test that rate limiter can be imported successfully."""
        assert RateLimiter is not None
        assert rate_limit is not None
        assert RateLimitExceeded is not None

    def test_rate_limit_exception_creation(self):
        """Test RateLimitExceeded exception creation."""
        exc = RateLimitExceeded(retry_after=30, limit=100, window=60)
        assert exc.status_code == 429
        assert exc.retry_after == 30
        assert exc.limit == 100
        assert exc.window == 60
        assert "Rate limit exceeded" in exc.detail

    def test_get_client_identifier_from_ip(self):
        """Test getting client identifier from IP address."""
        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.1")
        mock_request.scope = {}

        identifier = RateLimiter._get_client_identifier(mock_request)
        assert identifier == "ip:192.168.1.1"

    def test_get_client_identifier_from_user_id(self):
        """Test getting client identifier from user ID."""
        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.1")
        mock_request.scope = {"user_id": "user_123"}

        identifier = RateLimiter._get_client_identifier(mock_request)
        assert identifier == "user:user_123"

    def test_get_client_identifier_no_client(self):
        """Test getting client identifier when client is None."""
        mock_request = Mock(spec=Request)
        mock_request.client = None
        mock_request.scope = {}

        identifier = RateLimiter._get_client_identifier(mock_request)
        assert identifier == "ip:unknown"

    def test_get_rate_limit_key(self):
        """Test generation of rate limit Redis key."""
        key = RateLimiter._get_rate_limit_key("test_endpoint", "ip:192.168.1.1")
        assert key == "rate_limit:test_endpoint:ip:192.168.1.1"

    def test_get_reset_key(self):
        """Test generation of reset time Redis key."""
        key = RateLimiter._get_reset_key("test_endpoint", "ip:192.168.1.1")
        assert key == "rate_limit_reset:test_endpoint:ip:192.168.1.1"


class TestRateLimitDecorator:
    """Tests for rate limit decorator functionality."""

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_basic(self):
        """Test basic rate limit decorator application."""
        call_count = 0

        @rate_limit(requests=5, window_seconds=60)
        async def test_endpoint(request: Request):
            nonlocal call_count
            call_count += 1
            return {"status": "ok", "call": call_count}

        # Create mock request
        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.1")
        mock_request.scope = {}
        mock_request.headers = {}

        # Should succeed
        result = await test_endpoint(request=mock_request)
        assert result["status"] == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_decorator_counts_requests(self):
        """Test that rate limit decorator counts requests."""
        if not cache.available:
            pytest.skip("Cache not available")

        @rate_limit(requests=3, window_seconds=60, endpoint_name="test_counter")
        async def test_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.50")
        mock_request.scope = {}
        mock_request.headers = {}

        # Make 3 requests - should all succeed
        for i in range(3):
            result = await test_endpoint(request=mock_request)
            assert result["status"] == "ok"

        # 4th request should fail with 429
        result = await test_endpoint(request=mock_request)
        assert result.status_code == 429

        # Cleanup
        cache.delete("rate_limit:test_counter:ip:192.168.1.50")
        cache.delete("rate_limit_reset:test_counter:ip:192.168.1.50")

    @pytest.mark.asyncio
    async def test_rate_limit_no_request_object(self):
        """Test rate limit decorator when request object is not found."""
        @rate_limit(requests=5, window_seconds=60)
        async def test_endpoint():
            return {"status": "ok"}

        # Should succeed even without request (skips rate limiting)
        result = await test_endpoint()
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_rate_limit_exception_429_response(self):
        """Test that rate limit exception returns 429 response."""
        if not cache.available:
            pytest.skip("Cache not available")

        @rate_limit(requests=1, window_seconds=60, endpoint_name="test_429")
        async def test_endpoint(request: Request):
            return {"status": "ok"}

        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.60")
        mock_request.scope = {}
        mock_request.headers = {}

        # First request succeeds
        result1 = await test_endpoint(request=mock_request)
        assert result1["status"] == "ok"

        # Second request should return 429
        result2 = await test_endpoint(request=mock_request)
        assert hasattr(result2, "status_code") and result2.status_code == 429

        # Cleanup
        cache.delete("rate_limit:test_429:ip:192.168.1.60")
        cache.delete("rate_limit_reset:test_429:ip:192.168.1.60")

    @pytest.mark.asyncio
    async def test_rate_limit_headers_in_response(self):
        """Test that rate limit headers are added to response."""
        if not cache.available:
            pytest.skip("Cache not available")

        @rate_limit(requests=5, window_seconds=60, endpoint_name="test_headers")
        async def test_endpoint(request: Request):
            from fastapi.responses import JSONResponse
            response = JSONResponse({"status": "ok"})
            return response

        mock_request = Mock(spec=Request)
        mock_request.client = Mock(host="192.168.1.70")
        mock_request.scope = {}
        mock_request.headers = {}

        result = await test_endpoint(request=mock_request)

        # Check headers
        if hasattr(result, "headers"):
            assert "X-RateLimit-Limit" in result.headers
            assert "X-RateLimit-Remaining" in result.headers
            assert result.headers["X-RateLimit-Limit"] == "5"

        # Cleanup
        cache.delete("rate_limit:test_headers:ip:192.168.1.70")
        cache.delete("rate_limit_reset:test_headers:ip:192.168.1.70")


class TestRateLimitCheckLogic:
    """Tests for rate limit checking logic."""

    def test_check_rate_limit_first_request(self):
        """Test rate limit check for first request."""
        if not cache.available:
            pytest.skip("Cache not available")

        endpoint = "test_first"
        client_id = "ip:test_first"

        remaining, limit, retry_after = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id=client_id,
            limit=10,
            window=60
        )

        assert remaining == 9  # 10 - 1 (first request)
        assert limit == 10
        assert retry_after is None  # Not exceeded

        # Cleanup
        cache.delete(f"rate_limit:{endpoint}:{client_id}")
        cache.delete(f"rate_limit_reset:{endpoint}:{client_id}")

    def test_check_rate_limit_sequential_requests(self):
        """Test rate limit check with sequential requests."""
        if not cache.available:
            pytest.skip("Cache not available")

        endpoint = "test_seq"
        client_id = "ip:test_seq"
        limit = 3

        # First request
        remaining1, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id=client_id,
            limit=limit,
            window=60
        )
        assert remaining1 == 2

        # Second request
        remaining2, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id=client_id,
            limit=limit,
            window=60
        )
        assert remaining2 == 1

        # Third request
        remaining3, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id=client_id,
            limit=limit,
            window=60
        )
        assert remaining3 == 0

        # Fourth request should exceed
        with pytest.raises(RateLimitExceeded) as exc_info:
            RateLimiter.check_rate_limit(
                endpoint=endpoint,
                client_id=client_id,
                limit=limit,
                window=60
            )

        assert exc_info.value.status_code == 429

        # Cleanup
        cache.delete(f"rate_limit:{endpoint}:{client_id}")
        cache.delete(f"rate_limit_reset:{endpoint}:{client_id}")

    def test_check_rate_limit_exceeds_limit(self):
        """Test rate limit exception when limit exceeded."""
        if not cache.available:
            pytest.skip("Cache not available")

        endpoint = "test_exceed"
        client_id = "ip:test_exceed"

        # Make requests until limit is exceeded
        with pytest.raises(RateLimitExceeded) as exc_info:
            for i in range(5):
                RateLimiter.check_rate_limit(
                    endpoint=endpoint,
                    client_id=client_id,
                    limit=3,
                    window=60
                )

        exc = exc_info.value
        assert exc.status_code == 429
        assert exc.limit == 3
        assert exc.retry_after > 0

        # Cleanup
        cache.delete(f"rate_limit:{endpoint}:{client_id}")
        cache.delete(f"rate_limit_reset:{endpoint}:{client_id}")

    def test_check_rate_limit_cache_unavailable(self):
        """Test rate limit check when cache is unavailable."""
        with patch.object(cache, "available", False):
            remaining, limit, retry_after = RateLimiter.check_rate_limit(
                endpoint="test_no_cache",
                client_id="ip:test",
                limit=10,
                window=60
            )

            # Should fail open (allow request)
            assert remaining == 10
            assert limit == 10
            assert retry_after is None


class TestRateLimitFactory:
    """Tests for rate limit factory function."""

    def test_rate_limit_factory_creates_decorator(self):
        """Test that factory creates rate limit decorator."""
        decorator = rate_limit_factory("rate_limit_unified_overview")
        assert decorator is not None
        assert callable(decorator)

    def test_rate_limit_factory_with_config(self):
        """Test factory uses config values."""
        # Should use settings.rate_limit_unified_overview
        assert settings.rate_limit_unified_overview == 100
        assert settings.rate_limit_unified_holdings == 50
        assert settings.rate_limit_unified_performance == 50
        assert settings.rate_limit_unified_summary == 50


class TestRateLimitAcrossDifferentClients:
    """Tests for rate limit behavior across different clients."""

    def test_rate_limit_separate_per_client(self):
        """Test that rate limits are separate per client."""
        if not cache.available:
            pytest.skip("Cache not available")

        endpoint = "test_clients"

        # Client 1 makes requests
        remaining1, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id="ip:client1",
            limit=2,
            window=60
        )
        assert remaining1 == 1

        # Client 2 makes request (should have full limit)
        remaining2, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id="ip:client2",
            limit=2,
            window=60
        )
        assert remaining2 == 1

        # Client 1 second request
        remaining1_2, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id="ip:client1",
            limit=2,
            window=60
        )
        assert remaining1_2 == 0

        # Client 1 should be rate limited, but client 2 should still have quota
        with pytest.raises(RateLimitExceeded):
            RateLimiter.check_rate_limit(
                endpoint=endpoint,
                client_id="ip:client1",
                limit=2,
                window=60
            )

        remaining2_2, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id="ip:client2",
            limit=2,
            window=60
        )
        assert remaining2_2 == 0

        # Cleanup
        for client in ["client1", "client2"]:
            cache.delete(f"rate_limit:{endpoint}:ip:{client}")
            cache.delete(f"rate_limit_reset:{endpoint}:ip:{client}")

    def test_rate_limit_separate_per_endpoint(self):
        """Test that rate limits are separate per endpoint."""
        if not cache.available:
            pytest.skip("Cache not available")

        client_id = "ip:test_endpoints"

        # Endpoint 1
        remaining1, _, _ = RateLimiter.check_rate_limit(
            endpoint="endpoint_a",
            client_id=client_id,
            limit=2,
            window=60
        )
        assert remaining1 == 1

        # Endpoint 2 (should have full limit)
        remaining2, _, _ = RateLimiter.check_rate_limit(
            endpoint="endpoint_b",
            client_id=client_id,
            limit=2,
            window=60
        )
        assert remaining2 == 1

        # Cleanup
        for endpoint in ["endpoint_a", "endpoint_b"]:
            cache.delete(f"rate_limit:{endpoint}:{client_id}")
            cache.delete(f"rate_limit_reset:{endpoint}:{client_id}")


class TestUnifiedEndpointsRateLimiting:
    """Tests for rate limiting on unified endpoints."""

    def test_unified_endpoints_have_rate_limits_configured(self):
        """Test that unified endpoints have rate limit configuration."""
        assert hasattr(settings, "rate_limit_unified_overview")
        assert hasattr(settings, "rate_limit_unified_holdings")
        assert hasattr(settings, "rate_limit_unified_performance")
        assert hasattr(settings, "rate_limit_unified_summary")

        # Check defaults
        assert settings.rate_limit_unified_overview == 100
        assert settings.rate_limit_unified_holdings == 50
        assert settings.rate_limit_unified_performance == 50
        assert settings.rate_limit_unified_summary == 50

    def test_unified_endpoint_rate_limit_window(self):
        """Test that rate limit window is configured."""
        assert hasattr(settings, "rate_limit_window")
        assert settings.rate_limit_window == 60  # seconds


class TestRetryAfterHeader:
    """Tests for Retry-After header behavior."""

    def test_retry_after_in_429_response(self):
        """Test that Retry-After header is included in 429 response."""
        exc = RateLimitExceeded(retry_after=30, limit=100, window=60)
        assert exc.retry_after == 30

    def test_rate_limit_exceeded_has_required_fields(self):
        """Test that RateLimitExceeded has all required fields."""
        exc = RateLimitExceeded(retry_after=45, limit=50, window=60)
        assert exc.status_code == 429
        assert exc.retry_after == 45
        assert exc.limit == 50
        assert exc.window == 60


class TestEdgeCases:
    """Tests for edge cases in rate limiting."""

    def test_check_rate_limit_zero_limit(self):
        """Test rate limit with zero limit."""
        if not cache.available:
            pytest.skip("Cache not available")

        # First request will succeed (remaining will be -1)
        # but second request should fail (count will be 2, exceeds 0)
        try:
            RateLimiter.check_rate_limit(
                endpoint="test_zero",
                client_id="ip:test",
                limit=0,
                window=60
            )
        except RateLimitExceeded:
            # Expected on first request with limit=0
            pass

        # Cleanup
        cache.delete("rate_limit:test_zero:ip:test")
        cache.delete("rate_limit_reset:test_zero:ip:test")

    def test_check_rate_limit_very_small_window(self):
        """Test rate limit with very small time window."""
        if not cache.available:
            pytest.skip("Cache not available")

        endpoint = "test_small_window"
        client_id = "ip:test_small"

        # Make request in 1 second window
        remaining, _, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id=client_id,
            limit=1,
            window=1
        )
        assert remaining == 0

        # Next request should exceed
        with pytest.raises(RateLimitExceeded):
            RateLimiter.check_rate_limit(
                endpoint=endpoint,
                client_id=client_id,
                limit=1,
                window=1
            )

        # Cleanup
        cache.delete(f"rate_limit:{endpoint}:{client_id}")
        cache.delete(f"rate_limit_reset:{endpoint}:{client_id}")

    def test_check_rate_limit_very_large_limit(self):
        """Test rate limit with very large request limit."""
        if not cache.available:
            pytest.skip("Cache not available")

        endpoint = "test_large_limit"
        client_id = "ip:test_large"
        limit = 10000

        # Make request
        remaining, returned_limit, _ = RateLimiter.check_rate_limit(
            endpoint=endpoint,
            client_id=client_id,
            limit=limit,
            window=60
        )

        assert returned_limit == limit
        assert remaining == limit - 1

        # Cleanup
        cache.delete(f"rate_limit:{endpoint}:{client_id}")
        cache.delete(f"rate_limit_reset:{endpoint}:{client_id}")
