"""
Foreign exchange rate fetching and caching service.

Provides currency conversion for portfolio aggregation. Supports multiple sources
with caching and fallback strategies. Primary focus is EUR/USD conversion for
unified portfolio calculations.

Features:
- Current and historical FX rates
- Redis-based caching with TTL
- Multiple fallback strategies
- Rate limiting to avoid API throttling
- Graceful degradation when rates unavailable
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Tuple
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

try:
    import redis
    redis_available = True
except ImportError:
    redis_available = False

from app.services.price_fetcher import PriceFetcher
from app.config import settings

logger = logging.getLogger(__name__)

# Default fallback rates (approximate current market rates)
DEFAULT_FALLBACK_RATES = {
    ("USD", "EUR"): Decimal("0.92"),
    ("EUR", "USD"): Decimal("1.09"),
    ("GBP", "EUR"): Decimal("1.17"),
    ("EUR", "GBP"): Decimal("0.85"),
    ("USD", "GBP"): Decimal("0.79"),
    ("GBP", "USD"): Decimal("1.27"),
    ("CHF", "EUR"): Decimal("1.05"),
    ("EUR", "CHF"): Decimal("0.95"),
    ("JPY", "EUR"): Decimal("0.0063"),
    ("EUR", "JPY"): Decimal("159.00"),
}


class FXRateService:
    """Service for fetching, caching, and managing foreign exchange rates."""

    # Configuration constants
    CACHE_TTL_SECONDS = 3600  # 1 hour
    RATE_LIMIT_DELAY = 0.1  # 100ms between API calls
    MAX_RETRIES = 3

    def __init__(self):
        """Initialize the FX rate service."""
        self._redis_client = None
        self._redis_initialized = False
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="fx_rate")
        self._last_fetch_time: Dict[str, datetime] = {}

    @property
    def redis_client(self):
        """Lazy initialize Redis client for caching."""
        if redis_available and not self._redis_initialized:
            try:
                self._redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                self._redis_initialized = True
                logger.debug("Redis client initialized for FX rate caching")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis client for FX rates: {e}")
                self._redis_initialized = True  # Mark as attempted
        return self._redis_client

    async def get_current_rate(
        self,
        from_currency: str,
        to_currency: str,
        use_cache: bool = True,
        use_fallback: bool = True
    ) -> Decimal:
        """
        Get the current exchange rate from one currency to another.

        Args:
            from_currency: Source currency code (e.g., "USD")
            to_currency: Target currency code (e.g., "EUR")
            use_cache: Whether to check cache first (default True)
            use_fallback: Whether to use fallback rate on failure (default True)

        Returns:
            Exchange rate as Decimal (e.g., 0.92 for 1 USD = 0.92 EUR)

        Raises:
            ValueError: If rate cannot be fetched and use_fallback is False
        """
        # Same currency conversion
        if from_currency == to_currency:
            return Decimal("1.0")

        try:
            # Check cache first
            if use_cache:
                cached_rate = await self._get_cached_rate(from_currency, to_currency)
                if cached_rate is not None:
                    logger.debug(f"Cache hit for {from_currency}/{to_currency}: {cached_rate}")
                    return cached_rate

            # Fetch from source with retry logic
            rate = await self._fetch_with_retries(from_currency, to_currency)

            if rate is None:
                if use_fallback:
                    logger.warning(
                        f"Failed to fetch {from_currency}/{to_currency}, using fallback"
                    )
                    return self._get_fallback_rate(from_currency, to_currency)
                raise ValueError(f"Failed to fetch rate for {from_currency}/{to_currency}")

            # Cache the rate
            await self._cache_rate(from_currency, to_currency, rate)

            logger.info(f"Fetched {from_currency}/{to_currency}: {rate}")
            return rate

        except Exception as e:
            logger.error(f"Error getting rate {from_currency}/{to_currency}: {e}")
            if use_fallback:
                return self._get_fallback_rate(from_currency, to_currency)
            raise ValueError(f"Failed to get rate for {from_currency}/{to_currency}: {e}")

    async def get_historical_rate(
        self,
        from_currency: str,
        to_currency: str,
        target_date: date
    ) -> Optional[Decimal]:
        """
        Get the historical exchange rate for a specific date.

        Note: Yahoo Finance does not provide historical FX data directly.
        This implementation attempts to fetch the rate but falls back to
        current rate with a warning.

        Args:
            from_currency: Source currency code
            to_currency: Target currency code
            target_date: The date to fetch the rate for

        Returns:
            Exchange rate as Decimal, or None if not available
        """
        # Yahoo Finance doesn't have reliable historical FX data
        # For now, use current rate as approximation
        logger.warning(
            f"Historical FX rates not fully implemented. Using current rate for {target_date}"
        )
        try:
            return await self.get_current_rate(from_currency, to_currency)
        except Exception as e:
            logger.error(f"Failed to get historical rate for {target_date}: {e}")
            return None

    async def convert_amount(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        use_fallback: bool = True
    ) -> Decimal:
        """
        Convert an amount from one currency to another.

        Args:
            amount: The amount to convert
            from_currency: Source currency code
            to_currency: Target currency code
            use_fallback: Whether to use fallback rate on failure

        Returns:
            Converted amount as Decimal

        Raises:
            ValueError: If conversion fails and use_fallback is False
        """
        if from_currency == to_currency:
            return amount

        try:
            rate = await self.get_current_rate(
                from_currency,
                to_currency,
                use_fallback=use_fallback
            )
            return amount * rate
        except Exception as e:
            logger.error(f"Conversion failed: {amount} {from_currency} to {to_currency}: {e}")
            if use_fallback:
                rate = self._get_fallback_rate(from_currency, to_currency)
                return amount * rate
            raise

    async def get_rate_timestamp(self) -> datetime:
        """Get the timestamp of the last fetched rate."""
        return datetime.now(tz=datetime.now().astimezone().tzinfo)

    # Private helper methods

    async def _get_cached_rate(self, from_currency: str, to_currency: str) -> Optional[Decimal]:
        """Get cached rate from Redis if available."""
        if not self.redis_client:
            return None

        try:
            cache_key = f"fx_rate:{from_currency}:{to_currency}"
            cached = self.redis_client.get(cache_key)
            if cached:
                return Decimal(cached)
        except Exception as e:
            logger.debug(f"Cache get failed for {cache_key}: {e}")

        return None

    async def _cache_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        ttl_seconds: Optional[int] = None
    ) -> None:
        """Cache rate in Redis with TTL."""
        if not self.redis_client:
            return

        try:
            cache_key = f"fx_rate:{from_currency}:{to_currency}"
            ttl = ttl_seconds or self.CACHE_TTL_SECONDS
            self.redis_client.setex(cache_key, ttl, str(rate))
            logger.debug(f"Cached {from_currency}/{to_currency}: {rate} (TTL: {ttl}s)")
        except Exception as e:
            logger.warning(f"Cache set failed for {cache_key}: {e}")

    async def _fetch_with_retries(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """Fetch rate from source with retry logic."""
        for attempt in range(self.MAX_RETRIES):
            try:
                # Rate limit between requests
                if attempt > 0:
                    await asyncio.sleep(self.RATE_LIMIT_DELAY)

                rate = await self._fetch_rate_from_source(from_currency, to_currency)
                if rate is not None:
                    return rate

                logger.debug(
                    f"Attempt {attempt + 1}/{self.MAX_RETRIES} failed for "
                    f"{from_currency}/{to_currency}"
                )

            except Exception as e:
                logger.debug(
                    f"Attempt {attempt + 1}/{self.MAX_RETRIES} error fetching "
                    f"{from_currency}/{to_currency}: {e}"
                )

        return None

    async def _fetch_rate_from_source(
        self,
        from_currency: str,
        to_currency: str
    ) -> Optional[Decimal]:
        """Fetch FX rate from Yahoo Finance."""
        try:
            # Use Yahoo Finance FX ticker format: XXXYYYZZZ where
            # XXX = from_currency, YYY = to_currency, ZZZ = exchange
            # For EUR/USD, the Yahoo Finance ticker is EURUSD=X
            fx_ticker = f"{from_currency}{to_currency}=X"

            rate = await PriceFetcher.fetch_fx_rate(base=from_currency, quote=to_currency)

            # Validate rate is positive and non-zero
            if rate is None:
                logger.warning(f"No rate returned from Yahoo Finance: {fx_ticker}")
                return None

            if not isinstance(rate, (Decimal, int, float)):
                logger.warning(f"Invalid rate type from Yahoo Finance: {type(rate)}")
                return None

            rate_decimal = Decimal(str(rate)) if not isinstance(rate, Decimal) else rate

            if rate_decimal <= 0:
                logger.warning(f"Invalid rate value from Yahoo Finance: {fx_ticker} = {rate_decimal}")
                return None

            return rate_decimal

        except Exception as e:
            logger.error(f"Error fetching rate from Yahoo Finance: {e}")
            return None

    def _get_fallback_rate(self, from_currency: str, to_currency: str) -> Decimal:
        """Get fallback rate from default rates or inverse."""
        # Check direct mapping
        key = (from_currency, to_currency)
        if key in DEFAULT_FALLBACK_RATES:
            return DEFAULT_FALLBACK_RATES[key]

        # Check inverse mapping
        inverse_key = (to_currency, from_currency)
        if inverse_key in DEFAULT_FALLBACK_RATES:
            inverse_rate = DEFAULT_FALLBACK_RATES[inverse_key]
            if inverse_rate > 0:
                return Decimal(1) / inverse_rate

        # Default to 1.0 if no fallback available
        logger.warning(
            f"No fallback rate available for {from_currency}/{to_currency}, using 1.0"
        )
        return Decimal("1.0")


# Global instance
_fx_service: Optional[FXRateService] = None


def get_fx_service() -> FXRateService:
    """Get or create the global FX rate service instance."""
    global _fx_service
    if _fx_service is None:
        _fx_service = FXRateService()
    return _fx_service
