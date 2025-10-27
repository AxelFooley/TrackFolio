"""
Edge case tests for portfolio aggregator.

Tests critical edge cases:
- Empty portfolios
- Missing price data
- Division by zero scenarios
- Null values handling
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.portfolio_aggregator import PortfolioAggregator


pytestmark = pytest.mark.unit


class TestEmptyPortfolioEdgeCases:
    """Test edge cases with empty portfolios."""

    @pytest.mark.asyncio
    async def test_get_unified_holdings_empty(self):
        """Test get_unified_holdings with no positions or crypto portfolios."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        # Mock empty position results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Call should not raise exception
        holdings = await aggregator.get_unified_holdings()

        # Should return empty list
        assert holdings == []
        assert isinstance(holdings, list)

    @pytest.mark.asyncio
    async def test_get_unified_overview_empty(self):
        """Test get_unified_overview with empty portfolios."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        # Mock empty results
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        # Mock Redis as unavailable to skip caching
        aggregator._redis_client = None

        # Call should not raise exception
        overview = await aggregator.get_unified_overview()

        # Should return valid structure with zero values
        assert overview is not None
        assert isinstance(overview, dict)
        assert "total_value" in overview
        assert "total_profit" in overview

    @pytest.mark.asyncio
    async def test_safe_percentage_edge_cases(self):
        """Test _safe_percentage handles all edge cases."""
        # Test normal case
        result = PortfolioAggregator._safe_percentage(
            Decimal("100"), Decimal("1000")
        )
        assert result == 10.0

        # Test zero denominator
        result = PortfolioAggregator._safe_percentage(
            Decimal("100"), Decimal("0")
        )
        assert result is None

        # Test None denominator
        result = PortfolioAggregator._safe_percentage(
            Decimal("100"), None
        )
        assert result is None

        # Test negative values
        result = PortfolioAggregator._safe_percentage(
            Decimal("-50"), Decimal("1000")
        )
        assert result == -5.0

        # Test both zero
        result = PortfolioAggregator._safe_percentage(
            Decimal("0"), Decimal("0")
        )
        assert result is None


class TestCacheConstant:
    """Test that cache TTL constant is used correctly."""

    def test_cache_ttl_constant_exists(self):
        """Verify CACHE_TTL_SECONDS constant is defined."""
        assert hasattr(PortfolioAggregator, 'CACHE_TTL_SECONDS')
        assert PortfolioAggregator.CACHE_TTL_SECONDS == 60

    @pytest.mark.asyncio
    async def test_cache_ttl_constant_value(self):
        """Verify constant has expected value."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        # Check the constant through instance
        assert aggregator.CACHE_TTL_SECONDS == 60


class TestDataValidation:
    """Test data validation and error handling."""

    @pytest.mark.asyncio
    async def test_aggregate_portfolio_metrics_with_valid_data(self):
        """Test aggregation with valid traditional and crypto data."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        trad_overview = {
            "current_value": Decimal("10000"),
            "total_cost_basis": Decimal("8000"),
            "total_profit": Decimal("2000"),
            "today_gain_loss": Decimal("100")
        }

        crypto_overview = {
            "total_value": Decimal("5000"),
            "total_cost_basis": Decimal("4000"),
            "total_profit": Decimal("1000"),
            "today_change": Decimal("50")
        }

        result = await aggregator._aggregate_portfolio_metrics(
            trad_overview, crypto_overview
        )

        # Verify aggregation
        assert result["total_value"] == Decimal("15000")
        assert result["traditional_value"] == Decimal("10000")
        assert result["crypto_value"] == Decimal("5000")
        assert result["total_profit"] == Decimal("3000")
        assert result["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_aggregate_portfolio_metrics_zero_cost_basis(self):
        """Test aggregation when cost basis is zero."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        trad_overview = {
            "current_value": Decimal("10000"),
            "total_cost_basis": Decimal("0"),
            "total_profit": Decimal("10000"),
            "today_gain_loss": Decimal("100")
        }

        crypto_overview = {
            "total_value": Decimal("5000"),
            "total_cost_basis": Decimal("0"),
            "total_profit": Decimal("5000"),
            "today_change": Decimal("50")
        }

        result = await aggregator._aggregate_portfolio_metrics(
            trad_overview, crypto_overview
        )

        # Should handle zero cost basis gracefully
        assert result is not None
        assert result["total_profit_pct"] is None  # Can't calculate percentage


class TestRedisInitialization:
    """Test Redis client initialization pattern."""

    def test_redis_initialized_flag(self):
        """Test that _redis_initialized flag is properly managed."""
        mock_db = AsyncMock(spec=AsyncSession)
        aggregator = PortfolioAggregator(mock_db)

        # Initially should not be initialized
        assert not hasattr(aggregator, '_redis_initialized') or \
               aggregator._redis_initialized is False

        # Accessing redis_client should initialize it
        _ = aggregator.redis_client

        # After access, should be marked as initialized
        assert aggregator._redis_initialized is True
