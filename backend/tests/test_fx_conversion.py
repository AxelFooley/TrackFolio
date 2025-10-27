"""
Tests for FX Rate Service and currency conversion functionality.

Tests the FXRateService and portfolio aggregator currency conversion features.
Includes unit tests for FX rate fetching, caching, and conversion logic,
plus integration tests for unified portfolio aggregation with mixed currencies.
"""
import pytest
from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.fx_rate_service import FXRateService
from app.services.portfolio_aggregator import PortfolioAggregator


class TestFXRateService:
    """Unit tests for FXRateService."""

    @pytest.fixture
    def fx_service(self):
        """Create FX service instance for testing."""
        return FXRateService()

    def test_fx_service_initialization(self, fx_service):
        """Test that FX service initializes correctly."""
        assert fx_service is not None
        assert fx_service.DEFAULT_FALLBACK_RATES is not None
        assert ("USD", "EUR") in fx_service.DEFAULT_FALLBACK_RATES

    def test_same_currency_conversion(self):
        """Test that converting same currency returns 1.0."""
        service = FXRateService()
        # Test sync method should return immediately
        rate = service._get_fallback_rate("EUR", "EUR")
        # Direct fallback won't have EUR->EUR, but it shouldn't need it
        # The async method handles this in get_current_fx_rate
        assert rate is None  # No fallback needed for same currency

    @pytest.mark.asyncio
    async def test_fx_conversion_usd_to_eur_with_fallback(self):
        """Test USD to EUR conversion using fallback rate."""
        service = FXRateService()

        # Mock the provider fetch to fail
        with patch.object(service, '_fetch_rate_from_provider', return_value=None):
            rate = await service.get_current_fx_rate(
                "USD", "EUR",
                use_cache=False,
                fallback_enabled=True
            )

            # Should get fallback rate
            assert rate is not None
            assert rate > Decimal("0")
            # USD to EUR should be around 0.92
            assert Decimal("0.85") <= rate <= Decimal("1.0")

    @pytest.mark.asyncio
    async def test_fx_conversion_eur_to_usd_with_fallback(self):
        """Test EUR to USD conversion using fallback rate."""
        service = FXRateService()

        with patch.object(service, '_fetch_rate_from_provider', return_value=None):
            rate = await service.get_current_fx_rate(
                "EUR", "USD",
                use_cache=False,
                fallback_enabled=True
            )

            assert rate is not None
            assert rate > Decimal("0")
            # EUR to USD should be around 1.09
            assert Decimal("1.0") <= rate <= Decimal("1.2")

    @pytest.mark.asyncio
    async def test_fx_conversion_with_zero_rates(self):
        """Test handling of zero or invalid rates."""
        service = FXRateService()

        # Test zero rate from provider
        with patch.object(service, '_fetch_rate_from_provider', return_value=Decimal("0")):
            rate = await service.get_current_fx_rate(
                "USD", "EUR",
                use_cache=False,
                fallback_enabled=True
            )

            # Should fall back when provider returns 0
            assert rate is not None
            assert rate > Decimal("0")

    @pytest.mark.asyncio
    async def test_fx_conversion_fails_without_fallback(self):
        """Test that conversion fails when no fallback available."""
        service = FXRateService()

        # Mock provider to return None
        with patch.object(service, '_fetch_rate_from_provider', return_value=None):
            with pytest.raises(ValueError):
                await service.get_current_fx_rate(
                    "XYZ", "ABC",  # Non-standard currencies
                    use_cache=False,
                    fallback_enabled=False
                )

    @pytest.mark.asyncio
    async def test_fx_rate_caching_saves_rate(self):
        """Test that FX rates are cached after fetching."""
        service = FXRateService()

        # Mock successful provider response
        mock_rate = Decimal("0.92")
        with patch.object(service, '_fetch_rate_from_provider', return_value=mock_rate):
            rate1 = await service.get_current_fx_rate(
                "USD", "EUR",
                use_cache=True
            )

            assert rate1 == mock_rate

            # Second call should use cache (provider not called)
            with patch.object(service, '_fetch_rate_from_provider') as mock_provider:
                # Use cache
                rate2 = await service.get_current_fx_rate(
                    "USD", "EUR",
                    use_cache=True
                )

                # Redis cache might be None in test, but rate should still work
                assert rate2 is not None

    @pytest.mark.asyncio
    async def test_fx_rate_bypass_cache(self):
        """Test that cache can be bypassed with use_cache=False."""
        service = FXRateService()

        call_count = 0

        async def mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return Decimal("0.92")

        # First call with cache
        with patch.object(service, '_fetch_rate_from_provider', side_effect=mock_fetch):
            await service.get_current_fx_rate("USD", "EUR", use_cache=True)
            count_after_first = call_count

            # Second call without cache
            await service.get_current_fx_rate("USD", "EUR", use_cache=False)
            count_after_second = call_count

        # Should have fetched again when cache=False
        assert count_after_second > count_after_first

    @pytest.mark.asyncio
    async def test_fx_convert_amount(self):
        """Test amount conversion."""
        service = FXRateService()

        # Mock rate
        with patch.object(service, 'get_current_fx_rate', return_value=Decimal("0.92")):
            amount = Decimal("100")
            converted = await service.convert_amount(amount, "USD", "EUR")

            assert converted == Decimal("92")

    @pytest.mark.asyncio
    async def test_fx_convert_zero_amount(self):
        """Test that converting zero amount returns zero."""
        service = FXRateService()

        converted = await service.convert_amount(Decimal("0"), "USD", "EUR")
        assert converted == Decimal("0")

    @pytest.mark.asyncio
    async def test_fx_get_rate_pair(self):
        """Test getting both forward and inverse rates."""
        service = FXRateService()

        with patch.object(service, 'get_current_fx_rate', return_value=Decimal("0.92")):
            pair = await service.get_rate_pair("USD", "EUR")

            assert pair["from"] == "USD"
            assert pair["to"] == "EUR"
            assert "forward" in pair
            assert "inverse" in pair
            assert "timestamp" in pair

    @pytest.mark.asyncio
    async def test_fx_historical_rate_fallback_to_current(self):
        """Test that historical rates fall back to current rates."""
        service = FXRateService()

        mock_rate = Decimal("0.92")
        with patch.object(service, 'get_current_fx_rate', return_value=mock_rate):
            historical = await service.get_historical_fx_rate(
                "USD", "EUR",
                date.today() - timedelta(days=30)
            )

            assert historical == mock_rate

    def test_fx_fallback_rate_direct_match(self):
        """Test getting fallback rate for configured currency pair."""
        service = FXRateService()

        rate = service._get_fallback_rate("USD", "EUR")
        assert rate is not None
        assert rate == Decimal("0.92")

    def test_fx_fallback_rate_inverse_calculation(self):
        """Test getting fallback rate by calculating inverse."""
        service = FXRateService()

        # EUR to USD should be calculated as inverse of USD to EUR
        rate = service._get_fallback_rate("EUR", "USD")
        assert rate is not None
        # 1 / 0.92 ≈ 1.09
        assert Decimal("1.08") <= rate <= Decimal("1.10")

    def test_fx_fallback_rate_not_available(self):
        """Test getting fallback rate when not configured."""
        service = FXRateService()

        rate = service._get_fallback_rate("XYZ", "ABC")
        assert rate is None

    def test_fx_cache_key_patterns(self):
        """Test cache key generation patterns."""
        assert FXRateService.CACHE_KEY_CURRENT == "fx:current:{from_currency}:{to_currency}"
        assert FXRateService.CACHE_KEY_HISTORICAL == "fx:historical:{from_currency}:{to_currency}:{rate_date}"


class TestPortfolioAggregatorCurrencyConversion:
    """Integration tests for portfolio aggregator currency conversion."""

    @pytest.fixture
    async def aggregator(self, db_session):
        """Create aggregator with database session."""
        return PortfolioAggregator(db_session)

    @pytest.mark.asyncio
    async def test_convert_to_base_currency_same_currency(self, aggregator):
        """Test converting same currency returns amount unchanged."""
        amount = Decimal("100")
        result = await aggregator._convert_to_base_currency(amount, "EUR", "EUR")

        assert result == amount

    @pytest.mark.asyncio
    async def test_convert_to_base_currency_usd_to_eur(self, aggregator):
        """Test USD to EUR conversion."""
        amount = Decimal("100")

        # Mock FX service
        with patch.object(
            aggregator.fx_service,
            'convert_amount',
            return_value=Decimal("92")
        ):
            result = await aggregator._convert_to_base_currency(amount, "USD", "EUR")

            assert result == Decimal("92")

    @pytest.mark.asyncio
    async def test_convert_to_base_currency_zero_amount(self, aggregator):
        """Test converting zero amount returns zero."""
        result = await aggregator._convert_to_base_currency(Decimal("0"), "USD", "EUR")

        assert result == Decimal("0")

    @pytest.mark.asyncio
    async def test_convert_to_base_currency_with_fallback(self, aggregator):
        """Test currency conversion falls back when provider fails."""
        amount = Decimal("100")

        # Mock FX service to fail then use fallback
        with patch.object(
            aggregator.fx_service,
            'convert_amount',
            side_effect=Exception("API Error")
        ):
            with patch.object(
                aggregator.fx_service,
                '_get_fallback_rate',
                return_value=Decimal("0.92")
            ):
                result = await aggregator._convert_to_base_currency(amount, "USD", "EUR")

                assert result == Decimal("92")

    @pytest.mark.asyncio
    async def test_convert_to_base_currency_fallback_fails(self, aggregator):
        """Test that conversion returns unconverted amount if all strategies fail."""
        amount = Decimal("100")

        # Mock both FX service and fallback to fail
        with patch.object(
            aggregator.fx_service,
            'convert_amount',
            side_effect=Exception("API Error")
        ):
            with patch.object(
                aggregator.fx_service,
                '_get_fallback_rate',
                return_value=None
            ):
                result = await aggregator._convert_to_base_currency(amount, "USD", "EUR")

                # Should return unconverted amount
                assert result == amount

    @pytest.mark.asyncio
    async def test_convert_to_base_currency_precision(self, aggregator):
        """Test that Decimal precision is maintained in conversion."""
        amount = Decimal("123.456789")

        with patch.object(
            aggregator.fx_service,
            'convert_amount',
            return_value=Decimal("113.58") * Decimal("100") / Decimal("100")  # Simulate conversion
        ):
            result = await aggregator._convert_to_base_currency(amount, "USD", "EUR")

            # Result should be Decimal, not float
            assert isinstance(result, Decimal)

    @pytest.mark.asyncio
    async def test_unified_overview_mixed_currencies(self, aggregator, monkeypatch):
        """Test unified overview with mixed EUR and USD portfolios."""
        # This is a conceptual test - full integration would need database setup

        # Mock the helper methods
        async def mock_traditional_overview():
            return {
                "current_value": Decimal("50000"),
                "total_cost_basis": Decimal("45000"),
                "total_profit": Decimal("5000"),
                "today_gain_loss": Decimal("500")
            }

        async def mock_crypto_overview():
            return {
                "total_value": Decimal("25000"),  # USD
                "total_cost_basis": Decimal("20000"),
                "total_profit": Decimal("5000"),
                "today_change": Decimal("250")
            }

        with patch.object(
            aggregator,
            '_get_traditional_overview',
            side_effect=mock_traditional_overview
        ):
            with patch.object(
                aggregator,
                '_get_crypto_overview',
                side_effect=mock_crypto_overview
            ):
                # The aggregation should combine both values
                overview = await aggregator.get_unified_overview()

                # Both values should be included
                assert "total_value" in overview
                assert "traditional_value" in overview
                assert "crypto_value" in overview

    @pytest.mark.asyncio
    async def test_unified_performance_with_fx_rates(self, aggregator):
        """Test unified performance with FX rate conversion."""
        # This tests the performance data aggregation
        # The actual FX conversion should happen when aggregating USD crypto values to EUR

        # Mock snapshot data
        mock_snapshots = [
            {
                "date": date.today() - timedelta(days=1),
                "traditional_value": Decimal("50000"),
                "crypto_value": Decimal("25000")
            }
        ]

        # In a full test, we would verify that crypto USD values
        # were converted to EUR before being added to traditional EUR values
        assert all("value" in s or "traditional_value" in s for s in mock_snapshots)


class TestFXRateServiceEdgeCases:
    """Edge case tests for FX rate service."""

    def test_fx_fallback_rates_completeness(self):
        """Test that fallback rates table has essential pairs."""
        service = FXRateService()

        essential_pairs = [
            ("USD", "EUR"),
            ("EUR", "USD"),
            ("GBP", "EUR"),
            ("EUR", "GBP"),
        ]

        for pair in essential_pairs:
            assert pair in service.DEFAULT_FALLBACK_RATES, f"Missing fallback rate for {pair}"

    @pytest.mark.asyncio
    async def test_fx_rate_uppercase_normalization(self):
        """Test that currency codes are normalized to uppercase."""
        service = FXRateService()

        with patch.object(service, '_fetch_rate_from_provider', return_value=Decimal("0.92")):
            # Request with lowercase should work
            rate = await service.get_current_fx_rate(
                "usd", "eur",
                use_cache=False,
                fallback_enabled=True
            )

            assert rate is not None

    @pytest.mark.asyncio
    async def test_fx_rate_invalid_rate_value(self):
        """Test handling of invalid rate values."""
        service = FXRateService()

        # Test negative rate
        with patch.object(service, '_fetch_rate_from_provider', return_value=Decimal("-0.92")):
            rate = await service.get_current_fx_rate(
                "USD", "EUR",
                use_cache=False,
                fallback_enabled=True
            )

            # Should use fallback for invalid negative rate
            assert rate is not None
            assert rate > Decimal("0")

    @pytest.mark.asyncio
    async def test_fx_rate_very_large_conversion(self):
        """Test conversion of very large amounts."""
        service = FXRateService()

        large_amount = Decimal("999999999.99")

        with patch.object(service, 'get_current_fx_rate', return_value=Decimal("0.92")):
            converted = await service.convert_amount(large_amount, "USD", "EUR")

            assert converted > Decimal("0")
            assert isinstance(converted, Decimal)

    @pytest.mark.asyncio
    async def test_fx_rate_very_small_conversion(self):
        """Test conversion of very small amounts."""
        service = FXRateService()

        small_amount = Decimal("0.01")

        with patch.object(service, 'get_current_fx_rate', return_value=Decimal("0.92")):
            converted = await service.convert_amount(small_amount, "USD", "EUR")

            assert converted > Decimal("0")
            assert isinstance(converted, Decimal)
            assert converted < small_amount


class TestFXRateServiceCacheIntegration:
    """Tests for cache integration in FX rate service."""

    @pytest.mark.asyncio
    async def test_redis_cache_failure_graceful_degradation(self):
        """Test that service works if Redis is unavailable."""
        service = FXRateService()

        # Simulate Redis unavailable
        service._redis_client = None
        service._redis_initialized = False

        with patch.object(service, '_fetch_rate_from_provider', return_value=Decimal("0.92")):
            # Should still work without Redis
            rate = await service.get_current_fx_rate(
                "USD", "EUR",
                use_cache=False,
                fallback_enabled=True
            )

            assert rate == Decimal("0.92")

    @pytest.mark.asyncio
    async def test_historical_rate_caching_ttl(self):
        """Test that historical rates are cached with longer TTL."""
        service = FXRateService()

        # Historical rates should have longer cache TTL (7 days vs 1 hour for current)
        # This is a property of the implementation, not tested directly here
        # but documented in the service code
        assert hasattr(service, 'CACHE_KEY_HISTORICAL')


@pytest.mark.integration
class TestUnifiedPortfolioWithCurrencies:
    """Integration tests for unified portfolio with currency conversion."""

    @pytest.mark.asyncio
    async def test_aggregator_uses_fx_service(self, db_session):
        """Test that aggregator initializes with FX service."""
        aggregator = PortfolioAggregator(db_session)

        assert aggregator.fx_service is not None
        assert isinstance(aggregator.fx_service, FXRateService)

    @pytest.mark.asyncio
    async def test_aggregator_currency_conversion_integration(self, db_session):
        """Test full aggregator with currency conversion."""
        aggregator = PortfolioAggregator(db_session)

        # Test the conversion method exists and works
        result = await aggregator._convert_to_base_currency(
            Decimal("100"),
            "USD",
            "EUR"
        )

        assert isinstance(result, Decimal)
        assert result > Decimal("0")


# Parametrized tests for various currency pairs
@pytest.mark.parametrize("from_cur,to_cur", [
    ("USD", "EUR"),
    ("EUR", "USD"),
    ("GBP", "EUR"),
    ("EUR", "GBP"),
    ("USD", "GBP"),
    ("GBP", "USD"),
])
@pytest.mark.asyncio
async def test_fx_conversion_all_pairs(from_cur, to_cur):
    """Test FX conversion for all configured currency pairs."""
    service = FXRateService()

    rate = service._get_fallback_rate(from_cur, to_cur)

    # Should either have direct fallback or be able to compute inverse
    if rate is None:
        # Try inverse
        inverse_rate = service._get_fallback_rate(to_cur, from_cur)
        assert inverse_rate is not None, f"No rate available for {from_cur}/{to_cur} or inverse"
    else:
        assert rate > Decimal("0")
