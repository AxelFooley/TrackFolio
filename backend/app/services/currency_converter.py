"""
Currency conversion service.

Provides currency exchange rate fetching for converting between different currencies.
Uses Yahoo Finance as the primary data source via the PriceFetcher service.
"""
from decimal import Decimal
from typing import Optional
import logging
import asyncio
from datetime import datetime, timedelta

from app.services.price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)

# Simple in-memory cache for exchange rates
# Cache format: {('USD', 'EUR'): {'rate': Decimal('0.92'), 'timestamp': datetime}}
_rate_cache = {}
_cache_duration = timedelta(hours=1)  # Cache rates for 1 hour


def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """
    Get the current exchange rate from one currency to another.

    This function fetches the current exchange rate from Yahoo Finance,
    converting from_currency to to_currency. For example, get_exchange_rate("USD", "EUR")
    returns how many EUR equal 1 USD.

    Parameters:
        from_currency (str): Source currency code (e.g., "USD", "EUR", "GBP").
        to_currency (str): Target currency code (e.g., "USD", "EUR", "GBP").

    Returns:
        Decimal: Exchange rate where 1 unit of from_currency equals this many units of to_currency.

    Raises:
        ValueError: If the exchange rate cannot be fetched or is invalid.

    Example:
        >>> rate = get_exchange_rate("USD", "EUR")
        >>> # If rate is 0.92, then 1 USD = 0.92 EUR
        >>> usd_amount = Decimal("100")
        >>> eur_amount = usd_amount * rate  # 92 EUR
    """
    # Handle same currency conversion
    if from_currency == to_currency:
        logger.debug(f"Same currency conversion requested: {from_currency}")
        return Decimal("1.0")

    cache_key = (from_currency, to_currency)
    current_time = datetime.now()

    # Check if we have a cached rate that's still valid
    if cache_key in _rate_cache:
        cached_data = _rate_cache[cache_key]
        if current_time - cached_data['timestamp'] < _cache_duration:
            logger.debug(f"Using cached exchange rate for {from_currency}/{to_currency}: {cached_data['rate']}")
            return cached_data['rate']
        else:
            logger.debug(f"Cache expired for {from_currency}/{to_currency}, fetching fresh rate")
            del _rate_cache[cache_key]

    try:
        # Use PriceFetcher to get exchange rate
        # Note: Yahoo Finance uses base/quote format, so we need to call it with from_currency as base
        logger.info(f"Fetching exchange rate: {from_currency} -> {to_currency}")

        # Run the async function in a sync context
        rate = asyncio.run(_fetch_rate_async(from_currency, to_currency))

        if rate is None:
            raise ValueError(f"Failed to fetch exchange rate for {from_currency}/{to_currency}")

        # Cache the rate
        _rate_cache[cache_key] = {
            'rate': rate,
            'timestamp': current_time
        }

        logger.info(f"Exchange rate {from_currency}/{to_currency}: {rate} (cached)")
        return rate

    except Exception as e:
        logger.error(f"Error fetching exchange rate {from_currency}/{to_currency}: {e}")
        raise ValueError(f"Failed to fetch exchange rate for {from_currency}/{to_currency}: {e}")


async def _fetch_rate_async(from_currency: str, to_currency: str) -> Optional[Decimal]:
    """
    Internal async helper to fetch exchange rate from Yahoo Finance.

    Parameters:
        from_currency (str): Source currency code.
        to_currency (str): Target currency code.

    Returns:
        Optional[Decimal]: Exchange rate or None if unavailable.
    """
    try:
        rate = await PriceFetcher.fetch_fx_rate(base=from_currency, quote=to_currency)
        return rate
    except Exception as e:
        logger.error(f"Error in async rate fetch: {e}")
        return None


def clear_exchange_rate_cache():
    """
    Clear the exchange rate cache.

    This can be useful for forcing fresh rate fetching, for example
    at the start of a new trading day.
    """
    global _rate_cache
    cache_size = len(_rate_cache)
    _rate_cache.clear()
    logger.info(f"Cleared exchange rate cache (removed {cache_size} entries)")


def get_exchange_rate_with_fallback(
    from_currency: str,
    to_currency: str,
    fallback_rate: Optional[Decimal] = None
) -> Decimal:
    """
    Get exchange rate with a fallback value if the primary fetch fails.

    This is useful for non-critical operations where having a reasonable estimate
    is better than failing entirely.

    Parameters:
        from_currency (str): Source currency code.
        to_currency (str): Target currency code.
        fallback_rate (Optional[Decimal]): Rate to use if fetch fails.
            If None, uses hardcoded fallback rates.

    Returns:
        Decimal: Exchange rate (either fetched or fallback).

    Example:
        >>> # Try to fetch, but use 0.92 if it fails
        >>> rate = get_exchange_rate_with_fallback("USD", "EUR", Decimal("0.92"))
    """
    # Define some common fallback rates (approximate values)
    default_fallbacks = {
        ("USD", "EUR"): Decimal("0.92"),
        ("EUR", "USD"): Decimal("1.09"),
        ("GBP", "EUR"): Decimal("1.17"),
        ("EUR", "GBP"): Decimal("0.85"),
        ("USD", "GBP"): Decimal("0.79"),
        ("GBP", "USD"): Decimal("1.27"),
    }

    try:
        return get_exchange_rate(from_currency, to_currency)
    except Exception as e:
        logger.warning(
            f"Failed to fetch exchange rate {from_currency}/{to_currency}: {e}. "
            f"Using fallback rate."
        )

        # Use provided fallback or lookup default
        if fallback_rate is not None:
            return fallback_rate

        # Try to find a default fallback
        rate_key = (from_currency, to_currency)
        if rate_key in default_fallbacks:
            fallback = default_fallbacks[rate_key]
            logger.info(f"Using default fallback rate for {from_currency}/{to_currency}: {fallback}")
            return fallback

        # If no fallback available, raise error
        raise ValueError(
            f"No fallback rate available for {from_currency}/{to_currency}. "
            f"Please provide a fallback_rate parameter."
        )
