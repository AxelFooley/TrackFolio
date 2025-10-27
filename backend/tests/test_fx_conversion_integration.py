"""
Integration tests for currency conversion in portfolio aggregation.

Tests the unified portfolio aggregation endpoints with mixed currency portfolios.
These tests verify that USD crypto portfolios are properly converted to EUR
and aggregated with EUR traditional portfolios.
"""
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.portfolio_aggregator import PortfolioAggregator


@pytest.mark.unit
class TestPortfolioAggregatorCurrencyConversion:
    """Tests for portfolio aggregator currency conversion logic."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock AsyncSession."""
        return MagicMock()

    @pytest.fixture
    def aggregator(self, mock_db):
        """Create a PortfolioAggregator with mocked dependencies."""
        aggregator = PortfolioAggregator(mock_db)
        # Mock Redis to None for tests
        aggregator._redis_client = None
        aggregator._redis_initialized = True
        return aggregator

    @pytest.mark.asyncio
    async def test_convert_to_eur_same_currency(self, aggregator):
        """Test that converting EUR to EUR returns same amount."""
        amount = Decimal("1000.50")
        result = await aggregator._convert_to_eur(amount, "EUR")
        assert result == amount

    @pytest.mark.asyncio
    async def test_convert_to_eur_from_usd(self, aggregator):
        """Test converting USD amount to EUR."""
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            return_value=Decimal("0.92")
        ):
            amount = Decimal("25000")
            result = await aggregator._convert_to_eur(amount, "USD")
            expected = Decimal("25000") * Decimal("0.92")
            assert result == expected

    @pytest.mark.asyncio
    async def test_convert_to_eur_with_fallback(self, aggregator):
        """Test that conversion uses fallback when FX service fails."""
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            side_effect=Exception("API Error")
        ):
            amount = Decimal("25000")
            # Should not raise, should use warning and return original amount
            result = await aggregator._convert_to_eur(amount, "USD")
            # With fallback, should return original amount as it falls back safely
            assert result is not None

    @pytest.mark.asyncio
    async def test_conversion_accuracy_with_multiple_rates(self, aggregator):
        """Test conversion accuracy when handling multiple currency pairs."""
        # Test EUR (no conversion) + USD (convert)
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            return_value=Decimal("0.92")
        ):
            eur_amount = await aggregator._convert_to_eur(Decimal("50000"), "EUR")
            usd_amount = await aggregator._convert_to_eur(Decimal("25000"), "USD")

            total = eur_amount + usd_amount
            expected = Decimal("50000") + (Decimal("25000") * Decimal("0.92"))
            assert total == expected

    @pytest.mark.asyncio
    async def test_zero_amount_conversion(self, aggregator):
        """Test that zero amounts are handled correctly."""
        result = await aggregator._convert_to_eur(Decimal("0"), "USD")
        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_large_amount_conversion(self, aggregator):
        """Test conversion of large amounts maintains precision."""
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            return_value=Decimal("0.923456789")
        ):
            large_amount = Decimal("1000000.50")
            result = await aggregator._convert_to_eur(large_amount, "USD")
            expected = large_amount * Decimal("0.923456789")
            # Check that result has appropriate precision
            assert result == expected

    @pytest.mark.asyncio
    async def test_small_amount_conversion(self, aggregator):
        """Test conversion of small amounts maintains precision."""
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            return_value=Decimal("0.92")
        ):
            small_amount = Decimal("0.01")
            result = await aggregator._convert_to_eur(small_amount, "USD")
            expected = Decimal("0.0092")
            assert result == expected


@pytest.mark.unit
class TestCurrencyConversionEdgeCases:
    """Edge case tests for currency conversion."""

    @pytest.fixture
    def aggregator(self):
        """Create aggregator with mocked DB."""
        mock_db = MagicMock()
        agg = PortfolioAggregator(mock_db)
        agg._redis_client = None
        agg._redis_initialized = True
        return agg

    @pytest.mark.asyncio
    async def test_conversion_with_extreme_rate(self, aggregator):
        """Test conversion with very high or very low rates."""
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            return_value=Decimal("0.001")  # Very low rate
        ):
            amount = Decimal("1000")
            result = await aggregator._convert_to_eur(amount, "JPY")
            expected = Decimal("1")
            assert result == expected

    @pytest.mark.asyncio
    async def test_conversion_negative_amount_handling(self, aggregator):
        """Test that negative amounts are preserved (for P&L calculations)."""
        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            return_value=Decimal("0.92")
        ):
            # Negative amount (representing loss)
            amount = Decimal("-5000")
            result = await aggregator._convert_to_eur(amount, "USD")
            expected = Decimal("-5000") * Decimal("0.92")
            assert result == expected

    @pytest.mark.asyncio
    async def test_conversion_rate_changes_between_calls(self, aggregator):
        """Test handling rate changes between successive calls."""
        rates = [Decimal("0.92"), Decimal("0.91"), Decimal("0.93")]
        call_count = 0

        async def get_rate_side_effect(*args, **kwargs):
            nonlocal call_count
            result = rates[call_count]
            call_count += 1
            return result

        with patch.object(
            aggregator.fx_service,
            'get_current_rate',
            new_callable=AsyncMock,
            side_effect=get_rate_side_effect
        ):
            result1 = await aggregator._convert_to_eur(Decimal("100"), "USD")
            result2 = await aggregator._convert_to_eur(Decimal("100"), "USD")
            result3 = await aggregator._convert_to_eur(Decimal("100"), "USD")

            # Each conversion should use a different rate
            assert result1 == Decimal("92.00")
            assert result2 == Decimal("91.00")
            assert result3 == Decimal("93.00")


@pytest.mark.unit
class TestPortfolioAggregationWithConversion:
    """Test the aggregation flow with currency conversions."""

    @pytest.fixture
    def aggregator(self):
        """Create aggregator for testing."""
        mock_db = MagicMock()
        agg = PortfolioAggregator(mock_db)
        agg._redis_client = None
        agg._redis_initialized = True
        return agg

    @pytest.mark.asyncio
    async def test_aggregate_metrics_with_eur_portfolios(self, aggregator):
        """Test that EUR-only portfolios don't need conversion."""
        trad_overview = {
            "current_value": Decimal("50000"),
            "total_cost_basis": Decimal("45000"),
            "total_profit": Decimal("5000"),
            "today_gain_loss": Decimal("250")
        }

        crypto_overview = {
            "total_value": Decimal("20000"),
            "total_cost_basis": Decimal("18000"),
            "total_profit": Decimal("2000"),
            "today_change": Decimal("100")
        }

        result = await aggregator._aggregate_portfolio_metrics(trad_overview, crypto_overview)

        assert result["total_value"] == Decimal("70000")
        assert result["total_cost"] == Decimal("63000")
        assert result["total_profit"] == Decimal("7000")
        assert result["today_change"] == Decimal("350")
        assert result["currency"] == "EUR"

    @pytest.mark.asyncio
    async def test_profit_percentage_calculation(self, aggregator):
        """Test that profit percentage is correctly calculated."""
        trad_overview = {
            "current_value": Decimal("30000"),
            "total_cost_basis": Decimal("30000"),
            "total_profit": Decimal("0"),
            "today_gain_loss": Decimal("0")
        }

        crypto_overview = {
            "total_value": Decimal("20000"),
            "total_cost_basis": Decimal("18000"),
            "total_profit": Decimal("2000"),
            "today_change": Decimal("0")
        }

        result = await aggregator._aggregate_portfolio_metrics(trad_overview, crypto_overview)

        # Total profit: 2000, Total cost: 48000
        # 2000 / 48000 = 4.17%
        expected_pct = float((Decimal("2000") / Decimal("48000")) * 100)
        assert abs(result["total_profit_pct"] - expected_pct) < 0.01

    @pytest.mark.asyncio
    async def test_zero_portfolio_handling(self, aggregator):
        """Test aggregation when one portfolio is empty."""
        trad_overview = {
            "current_value": Decimal("0"),
            "total_cost_basis": Decimal("0"),
            "total_profit": Decimal("0"),
            "today_gain_loss": Decimal("0")
        }

        crypto_overview = {
            "total_value": Decimal("20000"),
            "total_cost_basis": Decimal("18000"),
            "total_profit": Decimal("2000"),
            "today_change": Decimal("100")
        }

        result = await aggregator._aggregate_portfolio_metrics(trad_overview, crypto_overview)

        assert result["total_value"] == Decimal("20000")
        assert result["traditional_value"] == Decimal("0")
        assert result["crypto_value"] == Decimal("20000")
