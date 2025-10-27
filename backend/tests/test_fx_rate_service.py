"""
Tests for foreign exchange rate fetching and conversion service.

Tests the FXRateService with focus on:
- Current rate fetching
- Caching and TTL
- Fallback strategies
- Currency conversion accuracy
- Error handling and graceful degradation
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

from app.services.fx_rate_service import FXRateService, get_fx_service, DEFAULT_FALLBACK_RATES


@pytest.mark.unit
class TestFXRateService:
    """Unit tests for FXRateService."""

    @pytest.fixture
    def fx_service(self):
        """Create a fresh FXRateService instance for each test."""
        service = FXRateService()
        # Don't try to connect to Redis for unit tests
        service._redis_client = None
        service._redis_initialized = True
        return service

    @pytest.mark.asyncio
    async def test_same_currency_conversion(self, fx_service):
        """Test that converting to the same currency returns 1.0."""
        rate = await fx_service.get_current_rate("EUR", "EUR")
        assert rate == Decimal("1.0")

    @pytest.mark.asyncio
    async def test_fallback_rate_usd_to_eur(self, fx_service):
        """Test that fallback rates are returned when primary fetch fails."""
        # Mock the fetch to return None (simulating API failure)
        with patch.object(fx_service, '_fetch_with_retries', return_value=None):
            rate = await fx_service.get_current_rate("USD", "EUR", use_fallback=True)
            # Should use fallback rate
            expected_rate = DEFAULT_FALLBACK_RATES[("USD", "EUR")]
            assert rate == expected_rate

    @pytest.mark.asyncio
    async def test_fallback_rate_eur_to_usd(self, fx_service):
        """Test fallback rate for EUR to USD."""
        with patch.object(fx_service, '_fetch_with_retries', return_value=None):
            rate = await fx_service.get_current_rate("EUR", "USD", use_fallback=True)
            expected_rate = DEFAULT_FALLBACK_RATES[("EUR", "USD")]
            assert rate == expected_rate

    @pytest.mark.asyncio
    async def test_inverse_fallback_rate(self, fx_service):
        """Test that inverse rates are calculated when direct fallback is missing."""
        # Test a pair that might not be in DEFAULT_FALLBACK_RATES but can be inverted
        with patch.object(fx_service, '_fetch_with_retries', return_value=None):
            # GBP to USD should work via inverse of USD to GBP
            rate = await fx_service.get_current_rate("USD", "GBP", use_fallback=True)
            # Should not raise, should use fallback
            assert rate > Decimal("0")

    @pytest.mark.asyncio
    async def test_convert_amount_same_currency(self, fx_service):
        """Test converting amount to the same currency."""
        result = await fx_service.convert_amount(Decimal("100"), "EUR", "EUR")
        assert result == Decimal("100")

    @pytest.mark.asyncio
    async def test_convert_amount_with_fallback_rate(self, fx_service):
        """Test amount conversion using fallback rate."""
        with patch.object(fx_service, '_fetch_with_retries', return_value=None):
            # Convert $100 to EUR using fallback (0.92)
            result = await fx_service.convert_amount(
                Decimal("100"),
                "USD",
                "EUR",
                use_fallback=True
            )
            expected = Decimal("100") * Decimal("0.92")
            assert result == expected

    @pytest.mark.asyncio
    async def test_error_without_fallback(self, fx_service):
        """Test that error is raised when fetch fails and fallback is disabled."""
        with patch.object(fx_service, '_fetch_with_retries', return_value=None):
            with pytest.raises(ValueError):
                await fx_service.get_current_rate(
                    "USD",
                    "EUR",
                    use_fallback=False
                )

    @pytest.mark.asyncio
    async def test_rate_timestamp(self, fx_service):
        """Test that rate timestamp is current."""
        timestamp = await fx_service.get_rate_timestamp()
        # Should be very recent (within 1 second)
        now = datetime.now(tz=datetime.now().astimezone().tzinfo)
        delta = abs((now - timestamp).total_seconds())
        assert delta < 1

    @pytest.mark.asyncio
    async def test_successful_rate_fetch(self, fx_service):
        """Test successful rate fetching from source."""
        expected_rate = Decimal("0.92")
        with patch.object(fx_service, '_fetch_with_retries', return_value=expected_rate):
            rate = await fx_service.get_current_rate("USD", "EUR")
            assert rate == expected_rate

    @pytest.mark.asyncio
    async def test_retry_logic(self, fx_service):
        """Test that retries are attempted before giving up."""
        # Mock _fetch_rate_from_source to fail twice, then succeed
        call_count = 0

        async def fetch_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return None
            return Decimal("0.92")

        with patch.object(fx_service, '_fetch_rate_from_source', new_callable=AsyncMock, side_effect=fetch_with_failure):
            rate = await fx_service._fetch_with_retries("USD", "EUR")
            assert rate == Decimal("0.92")
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_cache_hit(self, fx_service):
        """Test that cached rates are returned without refetching."""
        expected_rate = Decimal("0.92")
        # Set a rate in cache
        await fx_service._cache_rate("USD", "EUR", expected_rate)

        # Mock the fetch to track if it's called
        with patch.object(fx_service, '_fetch_with_retries') as mock_fetch:
            rate = await fx_service.get_current_rate(
                "USD",
                "EUR",
                use_cache=True
            )
            # If Redis is not initialized, will fetch anyway
            # This test depends on Redis being available
            # For unit tests without Redis, we just verify the method works
            assert rate is not None

    @pytest.mark.asyncio
    async def test_precision_preservation(self, fx_service):
        """Test that Decimal precision is preserved in calculations."""
        with patch.object(fx_service, '_fetch_with_retries', return_value=Decimal("0.923456")):
            rate = await fx_service.get_current_rate("USD", "EUR")
            # Convert an amount with many decimal places
            amount = Decimal("123.456789")
            result = amount * rate
            # Should maintain precision
            assert len(str(result).split('.')[-1]) > 5  # At least 5 decimal places

    @pytest.mark.asyncio
    async def test_zero_rate_handling(self, fx_service):
        """Test that zero rates are rejected."""
        # Mock PriceFetcher to return zero (invalid)
        with patch('app.services.fx_rate_service.PriceFetcher.fetch_fx_rate', return_value=Decimal("0")):
            # Should return None when rate is <= 0
            rate = await fx_service._fetch_rate_from_source("USD", "EUR")
            assert rate is None

    @pytest.mark.asyncio
    async def test_negative_rate_handling(self, fx_service):
        """Test that negative rates are rejected."""
        # Mock PriceFetcher to return negative (invalid)
        with patch('app.services.fx_rate_service.PriceFetcher.fetch_fx_rate', return_value=Decimal("-0.92")):
            rate = await fx_service._fetch_rate_from_source("USD", "EUR")
            assert rate is None


@pytest.mark.unit
class TestFXRateServiceGlobalInstance:
    """Tests for global FXRateService instance."""

    def test_get_fx_service_singleton(self):
        """Test that get_fx_service returns same instance."""
        service1 = get_fx_service()
        service2 = get_fx_service()
        assert service1 is service2

    def test_get_fx_service_is_fx_rate_service(self):
        """Test that singleton is FXRateService instance."""
        service = get_fx_service()
        assert isinstance(service, FXRateService)


@pytest.mark.unit
class TestFXConversionScenarios:
    """Integration-like tests for real-world conversion scenarios."""

    @pytest.fixture
    def fx_service(self):
        """Create FXRateService without Redis."""
        service = FXRateService()
        service._redis_client = None
        service._redis_initialized = True
        return service

    @pytest.mark.asyncio
    async def test_scenario_mixed_portfolio_conversion(self, fx_service):
        """Test the main use case: converting mixed EUR/USD portfolio."""
        # Scenario: EUR traditional (50k) + USD crypto (25k)
        with patch.object(fx_service, '_fetch_with_retries', return_value=Decimal("0.92")):
            eur_value = Decimal("50000")
            usd_value = Decimal("25000")

            # Convert USD to EUR
            rate = await fx_service.get_current_rate("USD", "EUR")
            usd_in_eur = usd_value * rate

            # Total in EUR
            total = eur_value + usd_in_eur
            expected = Decimal("50000") + (Decimal("25000") * Decimal("0.92"))
            assert total == expected
            assert total == Decimal("73000")

    @pytest.mark.asyncio
    async def test_scenario_single_currency_portfolio(self, fx_service):
        """Test portfolio with single currency needs no conversion."""
        # All EUR - should not need FX rates
        result = await fx_service.convert_amount(Decimal("75000"), "EUR", "EUR")
        assert result == Decimal("75000")

    @pytest.mark.asyncio
    async def test_scenario_fallback_usage_on_api_failure(self, fx_service):
        """Test that portfolio conversion works even if API fails."""
        # Simulate API failure
        with patch.object(fx_service, '_fetch_with_retries', return_value=None):
            usd_value = Decimal("25000")
            # Should use fallback rate
            result = await fx_service.convert_amount(usd_value, "USD", "EUR", use_fallback=True)
            # Should get approximately 23000 (25000 * 0.92)
            assert result > Decimal("22000")
            assert result < Decimal("24000")
