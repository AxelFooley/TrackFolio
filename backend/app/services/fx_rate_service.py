"""
FX Rate Service for currency conversion.

Provides functionality to fetch and cache foreign exchange rates for
converting between different currencies (primarily EUR/USD).

Supports multiple rate providers with fallback strategies:
- Primary: Yahoo Finance via PriceFetcher
- Fallback: Hardcoded reasonable estimates

Uses Redis for caching with configurable TTL to minimize API calls.
"""
from decimal import Decimal
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta, date
import logging

try:
    import redis
    redis_available = True
except ImportError:
    redis_available = False

from app.services.price_fetcher import PriceFetcher
from app.config import settings

logger = logging.getLogger(__name__)


class FXRateService:
    """Service for fetching and caching FX rates."""

    # Default fallback rates (approximate, updated occasionally)
    DEFAULT_FALLBACK_RATES = {
        ("USD", "EUR"): Decimal("0.92"),
        ("EUR", "USD"): Decimal("1.09"),
        ("GBP", "EUR"): Decimal("1.17"),
        ("EUR", "GBP"): Decimal("0.85"),
        ("USD", "GBP"): Decimal("0.79"),
        ("GBP", "USD"): Decimal("1.27"),
        ("CHF", "EUR"): Decimal("1.08"),
        ("EUR", "CHF"): Decimal("0.93"),
        ("JPY", "EUR"): Decimal("0.0067"),
        ("EUR", "JPY"): Decimal("149"),
    }

    # Cache key patterns
    CACHE_KEY_CURRENT = "fx:current:{from_currency}:{to_currency}"
    CACHE_KEY_HISTORICAL = "fx:historical:{from_currency}:{to_currency}:{rate_date}"

    def __init__(self):
        """Initialize FX Rate Service."""
        self.price_fetcher = PriceFetcher()
        self._redis_client = None
        self._redis_initialized = False

    @property
    def redis_client(self):
        """Lazy initialize Redis client for caching."""
        if redis_available and not self._redis_initialized:
            try:
                self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                self._redis_initialized = True
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client for FX rates: {e}")
                self._redis_initialized = True  # Mark as attempted
        return self._redis_client

    async def get_current_fx_rate(
        self,
        from_currency: str,
        to_currency: str,
        use_cache: bool = True,
        fallback_enabled: bool = True
    ) -> Decimal:
        """
        Get current exchange rate with optional caching.

        Fetches the current rate from Yahoo Finance, converting from_currency
        to to_currency. For example, get_current_fx_rate("USD", "EUR")
        returns how many EUR equal 1 USD.

        Args:
            from_currency: Source currency code (e.g., "USD", "EUR", "GBP")
            to_currency: Target currency code (e.g., "USD", "EUR", "GBP")
            use_cache: Whether to check cache first (default True)
            fallback_enabled: Whether to use fallback rate if fetch fails (default True)

        Returns:
            Decimal: Exchange rate where 1 unit of from_currency equals
                    this many units of to_currency.

        Raises:
            ValueError: If rate cannot be fetched and fallback_enabled is False

        Example:
            >>> rate = await fx_service.get_current_fx_rate("USD", "EUR")
            >>> # If rate is 0.92, then 1 USD = 0.92 EUR
            >>> usd_amount = Decimal("100")
            >>> eur_amount = usd_amount * rate  # 92 EUR
        """
        # Handle same currency conversion
        if from_currency == to_currency:
            logger.debug(f"Same currency conversion requested: {from_currency}")
            return Decimal("1.0")

        # Normalize currency codes to uppercase
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Check cache if enabled
        if use_cache:
            cached_rate = await self._get_cached_rate(from_currency, to_currency)
            if cached_rate is not None:
                logger.debug(f"Returning cached FX rate: {from_currency}/{to_currency} = {cached_rate}")
                return cached_rate

        # Try to fetch rate from provider
        try:
            rate = await self._fetch_rate_from_provider(from_currency, to_currency)
            if rate is not None and rate > Decimal("0"):
                # Cache the rate if successful
                await self._cache_rate(from_currency, to_currency, rate)
                logger.info(f"Fetched FX rate: {from_currency}/{to_currency} = {rate}")
                return rate
        except Exception as e:
            logger.warning(f"Error fetching FX rate from provider: {e}")

        # Use fallback if enabled
        if fallback_enabled:
            fallback_rate = self._get_fallback_rate(from_currency, to_currency)
            if fallback_rate is not None:
                logger.info(
                    f"Using fallback FX rate for {from_currency}/{to_currency}: {fallback_rate}"
                )
                return fallback_rate

        # No rate available
        raise ValueError(
            f"Failed to fetch FX rate for {from_currency}/{to_currency} "
            f"and no fallback available"
        )

    async def get_historical_fx_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        fallback_enabled: bool = True
    ) -> Decimal:
        """
        Get historical exchange rate for a specific date.

        Used for performance calculations where historical FX rates are needed.
        Currently uses current rates as fallback since Yahoo Finance API
        access to historical rates is limited.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date for which to get the rate
            fallback_enabled: Whether to use current rate if historical unavailable

        Returns:
            Decimal: Exchange rate for the specified date

        Raises:
            ValueError: If rate cannot be fetched and fallback disabled
        """
        if from_currency == to_currency:
            return Decimal("1.0")

        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        # Check cache for historical rate
        cached_rate = await self._get_cached_historical_rate(from_currency, to_currency, rate_date)
        if cached_rate is not None:
            logger.debug(
                f"Returning cached historical FX rate: "
                f"{from_currency}/{to_currency} on {rate_date} = {cached_rate}"
            )
            return cached_rate

        # Note: Yahoo Finance doesn't provide easy historical rate access through PriceFetcher
        # For now, we use current rates as approximation
        # In production, consider using a dedicated FX API (e.g., OpenExchangeRates, ECB)
        logger.debug(
            f"Historical rate unavailable for {rate_date}, "
            f"falling back to current rate for {from_currency}/{to_currency}"
        )

        try:
            current_rate = await self.get_current_fx_rate(
                from_currency,
                to_currency,
                use_cache=False,
                fallback_enabled=fallback_enabled
            )
            # Cache the historical rate
            await self._cache_historical_rate(from_currency, to_currency, rate_date, current_rate)
            return current_rate
        except ValueError as e:
            if not fallback_enabled:
                raise
            # Use fallback
            fallback_rate = self._get_fallback_rate(from_currency, to_currency)
            if fallback_rate is not None:
                logger.warning(
                    f"Using fallback rate for {from_currency}/{to_currency} on {rate_date}"
                )
                return fallback_rate
            raise ValueError(
                f"Failed to get historical FX rate for {from_currency}/{to_currency} on {rate_date}"
            )

    async def convert_amount(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        rate_date: Optional[date] = None
    ) -> Decimal:
        """
        Convert an amount from one currency to another.

        Convenience method that combines rate fetching and multiplication.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Optional date for historical conversion (None = current)

        Returns:
            Decimal: Converted amount

        Example:
            >>> amount = await fx_service.convert_amount(
            ...     Decimal("100"), "USD", "EUR"
            ... )  # 92 EUR (assuming 1 USD = 0.92 EUR)
        """
        if amount == Decimal("0"):
            return Decimal("0")

        if rate_date is None:
            rate = await self.get_current_fx_rate(from_currency, to_currency)
        else:
            rate = await self.get_historical_fx_rate(from_currency, to_currency, rate_date)

        return amount * rate

    async def get_rate_pair(
        self,
        from_currency: str,
        to_currency: str
    ) -> Dict[str, Decimal]:
        """
        Get both forward and inverse rates for a currency pair.

        Useful for displaying exchange rate information in both directions.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Dictionary with 'forward' and 'inverse' rates
        """
        forward = await self.get_current_fx_rate(from_currency, to_currency)
        inverse = await self.get_current_fx_rate(to_currency, from_currency)

        return {
            "from": from_currency,
            "to": to_currency,
            "forward": forward,  # 1 from_currency = forward to_currency
            "inverse": inverse,  # 1 to_currency = inverse from_currency
            "timestamp": datetime.utcnow().isoformat()
        }

    # Private helper methods

    async def _fetch_rate_from_provider(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """
        Fetch exchange rate from Yahoo Finance provider.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Decimal rate or None if unavailable
        """
        try:
            # Use PriceFetcher to get exchange rate
            # Yahoo Finance symbol format for currencies: FROM+TO=X
            # e.g., EURUSD=X for EUR to USD
            rate = await self.price_fetcher.fetch_fx_rate(
                base=from_currency,
                quote=to_currency
            )
            return rate
        except Exception as e:
            logger.error(
                f"Failed to fetch FX rate from provider for {from_currency}/{to_currency}: {e}"
            )
            return None

    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """
        Get fallback exchange rate from hardcoded defaults.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Decimal rate or None if not available in fallback table
        """
        key = (from_currency, to_currency)

        # Check direct match
        if key in self.DEFAULT_FALLBACK_RATES:
            return self.DEFAULT_FALLBACK_RATES[key]

        # Try inverse and calculate reciprocal
        inverse_key = (to_currency, from_currency)
        if inverse_key in self.DEFAULT_FALLBACK_RATES:
            try:
                inverse_rate = self.DEFAULT_FALLBACK_RATES[inverse_key]
                if inverse_rate > Decimal("0"):
                    return Decimal("1") / inverse_rate
            except Exception as e:
                logger.warning(f"Error calculating inverse rate: {e}")

        return None

    async def _cache_rate(self, from_currency: str, to_currency: str, rate: Decimal) -> None:
        """
        Cache current exchange rate in Redis.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate: Exchange rate to cache
        """
        if not self.redis_client:
            return

        try:
            cache_key = self.CACHE_KEY_CURRENT.format(
                from_currency=from_currency,
                to_currency=to_currency
            )
            ttl_seconds = settings.fx_cache_ttl_hours * 3600
            self.redis_client.setex(cache_key, ttl_seconds, str(rate))
            logger.debug(f"Cached FX rate {cache_key} = {rate} (TTL: {ttl_seconds}s)")
        except Exception as e:
            logger.warning(f"Failed to cache FX rate: {e}")

    async def _cache_historical_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date,
        rate: Decimal
    ) -> None:
        """
        Cache historical exchange rate in Redis.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date of the rate
            rate: Exchange rate to cache
        """
        if not self.redis_client:
            return

        try:
            cache_key = self.CACHE_KEY_HISTORICAL.format(
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date=rate_date.isoformat()
            )
            # Historical rates cached longer (7 days)
            ttl_seconds = 7 * 24 * 3600
            self.redis_client.setex(cache_key, ttl_seconds, str(rate))
            logger.debug(
                f"Cached historical FX rate {cache_key} = {rate} (TTL: {ttl_seconds}s)"
            )
        except Exception as e:
            logger.warning(f"Failed to cache historical FX rate: {e}")

    async def _get_cached_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """
        Get cached current exchange rate from Redis.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            Decimal rate or None if not cached or expired
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self.CACHE_KEY_CURRENT.format(
                from_currency=from_currency,
                to_currency=to_currency
            )
            cached_value = self.redis_client.get(cache_key)
            if cached_value:
                return Decimal(cached_value)
        except Exception as e:
            logger.warning(f"Failed to get cached FX rate: {e}")

        return None

    async def _get_cached_historical_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate_date: date
    ) -> Optional[Decimal]:
        """
        Get cached historical exchange rate from Redis.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            rate_date: Date of the rate

        Returns:
            Decimal rate or None if not cached or expired
        """
        if not self.redis_client:
            return None

        try:
            cache_key = self.CACHE_KEY_HISTORICAL.format(
                from_currency=from_currency,
                to_currency=to_currency,
                rate_date=rate_date.isoformat()
            )
            cached_value = self.redis_client.get(cache_key)
            if cached_value:
                return Decimal(cached_value)
        except Exception as e:
            logger.warning(f"Failed to get cached historical FX rate: {e}")

        return None


# Singleton instance
_fx_service_instance = None


def get_fx_service() -> FXRateService:
    """
    Get or create the FX Rate Service singleton.

    Returns:
        FXRateService: Global FX rate service instance
    """
    global _fx_service_instance
    if _fx_service_instance is None:
        _fx_service_instance = FXRateService()
    return _fx_service_instance
