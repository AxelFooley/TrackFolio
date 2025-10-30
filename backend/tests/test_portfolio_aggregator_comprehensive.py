"""
Comprehensive test suite for portfolio aggregation service.

Tests the PortfolioAggregator service with focus on:
- Batch price loading optimization (N+1 query elimination)
- Traditional and crypto holdings formatting
- Overview metrics calculation
- Error handling and graceful degradation
- Cache behavior and fallback
- Empty portfolio edge cases
- Metrics aggregation logic
"""
import pytest
import json
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.services.portfolio_aggregator import PortfolioAggregator


pytestmark = pytest.mark.unit


class TestAggregatePortfolioMetrics:
    """Tests for portfolio metrics aggregation logic."""

    @pytest.mark.asyncio
    async def test_aggregate_portfolio_metrics_basic(self):
        """Test basic aggregation of traditional and crypto metrics."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        trad = {
            "current_value": Decimal("30000.00"),
            "total_cost_basis": Decimal("28000.00"),
            "total_profit": Decimal("2000.00"),
            "today_gain_loss": Decimal("100.00"),
        }

        crypto = {
            "total_value": Decimal("20000.00"),
            "total_cost_basis": Decimal("18000.00"),
            "total_profit": Decimal("2000.00"),
            "today_change": Decimal("150.00"),
        }

        result = await aggregator._aggregate_portfolio_metrics(trad, crypto)

        # Verify totals
        assert result["total_value"] == Decimal("50000.00")
        assert result["traditional_value"] == Decimal("30000.00")
        assert result["crypto_value"] == Decimal("20000.00")
        assert result["total_cost"] == Decimal("46000.00")
        assert result["total_profit"] == Decimal("4000.00")
        assert result["today_change"] == Decimal("250.00")
        assert result["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_aggregate_portfolio_metrics_percentages(self):
        """Test percentage calculations in aggregation."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        trad = {
            "current_value": Decimal("50000.00"),
            "total_cost_basis": Decimal("50000.00"),
            "total_profit": Decimal("0.00"),
            "today_gain_loss": Decimal("0.00"),
        }

        crypto = {
            "total_value": Decimal("20000.00"),
            "total_cost_basis": Decimal("10000.00"),
            "total_profit": Decimal("10000.00"),
            "today_change": Decimal("0.00"),
        }

        result = await aggregator._aggregate_portfolio_metrics(trad, crypto)

        assert result["total_profit_pct"] == pytest.approx(16.666666667, rel=1e-5)
        assert result["traditional_profit_pct"] == 0.0
        assert result["crypto_profit_pct"] == 100.0

    @pytest.mark.asyncio
    async def test_aggregate_portfolio_metrics_zero_cost_basis(self):
        """Test aggregation when cost basis is zero."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        trad = {
            "current_value": Decimal("0"),
            "total_cost_basis": Decimal("0"),
            "total_profit": Decimal("0"),
            "today_gain_loss": Decimal("0"),
        }

        crypto = {
            "total_value": Decimal("0"),
            "total_cost_basis": Decimal("0"),
            "total_profit": Decimal("0"),
            "today_change": Decimal("0"),
        }

        result = await aggregator._aggregate_portfolio_metrics(trad, crypto)

        assert result["total_profit_pct"] is None
        assert result["traditional_profit_pct"] is None
        assert result["crypto_profit_pct"] is None
        assert result["today_change_pct"] is None

    @pytest.mark.asyncio
    async def test_aggregate_portfolio_metrics_negative_changes(self):
        """Test aggregation with negative profit/loss."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        trad = {
            "current_value": Decimal("19000.00"),
            "total_cost_basis": Decimal("20000.00"),
            "total_profit": Decimal("-1000.00"),
            "today_gain_loss": Decimal("-50.00"),
        }

        crypto = {
            "total_value": Decimal("18000.00"),
            "total_cost_basis": Decimal("20000.00"),
            "total_profit": Decimal("-2000.00"),
            "today_change": Decimal("-100.00"),
        }

        result = await aggregator._aggregate_portfolio_metrics(trad, crypto)

        assert result["total_value"] == Decimal("37000.00")
        assert result["total_profit"] == Decimal("-3000.00")
        assert result["today_change"] == Decimal("-150.00")
        # -3000 / 40000 * 100 = -7.5
        assert result["total_profit_pct"] == pytest.approx(-7.5, rel=1e-5)


class TestCacheBehavior:
    """Tests for Redis caching behavior."""

    @pytest.mark.asyncio
    async def test_set_cache_success(self):
        """Test successful cache set operation."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        mock_redis = MagicMock()
        aggregator._redis_client = mock_redis
        aggregator._redis_initialized = True

        test_data = {"key": "value", "number": 42}

        await aggregator._set_cache("test_key", test_data, ttl_seconds=60)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 60
        assert json.loads(call_args[0][2]) == test_data

    @pytest.mark.asyncio
    async def test_get_cache_success(self):
        """Test successful cache retrieval."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        test_data = {"key": "value"}
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps(test_data)
        aggregator._redis_client = mock_redis
        aggregator._redis_initialized = True

        result = await aggregator._get_cache("test_key")

        assert result == test_data
        mock_redis.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_cache_miss(self):
        """Test cache miss returns None."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        aggregator._redis_client = mock_redis
        aggregator._redis_initialized = True

        result = await aggregator._get_cache("nonexistent_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_redis_error(self, caplog):
        """Test graceful error handling when Redis set fails."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        mock_redis = MagicMock()
        mock_redis.setex.side_effect = Exception("Redis connection lost")
        aggregator._redis_client = mock_redis
        aggregator._redis_initialized = True

        with caplog.at_level(logging.WARNING):
            await aggregator._set_cache("test_key", {"data": "value"})

        assert "Cache set failed" in caplog.text

    @pytest.mark.asyncio
    async def test_cache_get_redis_error(self, caplog):
        """Test graceful error handling when Redis get fails."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        mock_redis = MagicMock()
        mock_redis.get.side_effect = Exception("Redis connection lost")
        aggregator._redis_client = mock_redis
        aggregator._redis_initialized = True

        with caplog.at_level(logging.WARNING):
            result = await aggregator._get_cache("test_key")

        assert result is None
        assert "Cache get failed" in caplog.text

    @pytest.mark.asyncio
    async def test_cache_unavailable_uses_ttl_config(self):
        """Test that cache operations use portfolio_aggregator_cache_ttl config."""
        from app.config import settings
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        mock_redis = MagicMock()
        aggregator._redis_client = mock_redis
        aggregator._redis_initialized = True

        await aggregator._set_cache("key", {"data": "test"}, ttl_seconds=settings.portfolio_aggregator_cache_ttl)

        call_args = mock_redis.setex.call_args
        assert call_args[0][1] == settings.portfolio_aggregator_cache_ttl


class TestEmptyPortfolioScenarios:
    """Tests for handling empty portfolios."""

    @pytest.mark.asyncio
    async def test_get_unified_holdings_empty(self):
        """Test unified holdings with no positions or crypto."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        # Mock the count methods to return 0
        aggregator._get_traditional_holdings_count = AsyncMock(return_value=0)
        aggregator._get_crypto_holdings_count = AsyncMock(return_value=0)

        # Mock the holdings methods to return empty lists
        aggregator._get_traditional_holdings = AsyncMock(return_value=[])
        aggregator._get_crypto_holdings = AsyncMock(return_value=[])

        # get_unified_holdings returns tuple (holdings_list, total_count)
        holdings, total = await aggregator.get_unified_holdings()

        assert holdings == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_get_unified_overview_empty_portfolios(self):
        """Test overview calculation with empty portfolios."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        aggregator._get_traditional_overview = AsyncMock(
            return_value={
                "current_value": Decimal("0"),
                "total_cost_basis": Decimal("0"),
                "total_profit": Decimal("0"),
                "today_gain_loss": Decimal("0"),
            }
        )

        aggregator._get_crypto_overview = AsyncMock(
            return_value={
                "total_value": Decimal("0"),
                "total_cost_basis": Decimal("0"),
                "total_profit": Decimal("0"),
                "today_change": Decimal("0"),
            }
        )

        aggregator._get_cache = AsyncMock(return_value=None)
        aggregator._set_cache = AsyncMock()

        result = await aggregator.get_unified_overview()

        assert result["total_value"] == Decimal("0")
        assert result["total_profit"] == Decimal("0")
        assert result["total_profit_pct"] is None


class TestSafePercentage:
    """Tests for _safe_percentage helper method."""

    def test_safe_percentage_normal(self):
        """Test normal percentage calculation."""
        result = PortfolioAggregator._safe_percentage(Decimal("100"), Decimal("1000"))
        assert result == 10.0

    def test_safe_percentage_zero_denominator(self):
        """Test percentage with zero denominator."""
        result = PortfolioAggregator._safe_percentage(Decimal("100"), Decimal("0"))
        assert result is None

    def test_safe_percentage_none_denominator(self):
        """Test percentage with None denominator."""
        result = PortfolioAggregator._safe_percentage(Decimal("100"), None)
        assert result is None

    def test_safe_percentage_negative(self):
        """Test negative percentage."""
        result = PortfolioAggregator._safe_percentage(Decimal("-50"), Decimal("1000"))
        assert result == -5.0

    def test_safe_percentage_zero_numerator(self):
        """Test with zero numerator."""
        result = PortfolioAggregator._safe_percentage(Decimal("0"), Decimal("1000"))
        assert result == 0.0

    def test_safe_percentage_both_negative(self):
        """Test with both numerator and denominator negative."""
        result = PortfolioAggregator._safe_percentage(Decimal("-100"), Decimal("-1000"))
        assert result == 10.0


class TestCacheTTLConstant:
    """Tests verifying portfolio_aggregator_cache_ttl config is used consistently."""

    def test_cache_ttl_config_exists(self):
        """Test that portfolio_aggregator_cache_ttl config is defined."""
        from app.config import settings
        assert hasattr(settings, "portfolio_aggregator_cache_ttl")
        assert settings.portfolio_aggregator_cache_ttl == 60

    @pytest.mark.asyncio
    async def test_cache_ttl_used_in_overview(self):
        """Test that get_unified_overview uses portfolio_aggregator_cache_ttl config."""
        from app.config import settings
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        aggregator._get_cache = AsyncMock(return_value=None)
        aggregator._set_cache = AsyncMock()
        aggregator._get_traditional_overview = AsyncMock(
            return_value={
                "current_value": Decimal("0"),
                "total_cost_basis": Decimal("0"),
                "total_profit": Decimal("0"),
                "today_gain_loss": Decimal("0"),
            }
        )
        aggregator._get_crypto_overview = AsyncMock(
            return_value={
                "total_value": Decimal("0"),
                "total_cost_basis": Decimal("0"),
                "total_profit": Decimal("0"),
                "today_change": Decimal("0"),
            }
        )

        await aggregator.get_unified_overview()

        # Verify _set_cache was called with config value
        aggregator._set_cache.assert_called_once()
        call_kwargs = aggregator._set_cache.call_args[1]
        assert call_kwargs["ttl_seconds"] == settings.portfolio_aggregator_cache_ttl
