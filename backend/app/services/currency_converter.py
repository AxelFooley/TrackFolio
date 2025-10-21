"""
Currency conversion service.

Provides currency exchange rate fetching for converting between different currencies.
Uses Yahoo Finance as the primary data source via the PriceFetcher service.
"""
from decimal import Decimal
from typing import Optional
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.services.price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)

# Thread pool executor for running sync functions in async contexts
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="currency_converter")


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

    try:
        # Use PriceFetcher to get exchange rate
        # Note: Yahoo Finance uses base/quote format, so we need to call it with from_currency as base
        logger.info(f"Fetching exchange rate: {from_currency} -> {to_currency}")

        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context - submit to executor to run in a separate thread
            # This avoids "Cannot run the event loop while another loop is running" error
            future = _executor.submit(_fetch_rate_sync, from_currency, to_currency)
            rate = future.result(timeout=30)  # concurrent.futures.Future supports timeout
        except RuntimeError:
            # No running loop, safe to use synchronous call directly
            rate = _fetch_rate_sync(from_currency, to_currency)

        if rate is None:
            raise ValueError(f"Failed to fetch exchange rate for {from_currency}/{to_currency}")

        logger.info(f"Exchange rate {from_currency}/{to_currency}: {rate}")
        return rate

    except Exception as e:
        logger.error(f"Error fetching exchange rate {from_currency}/{to_currency}: {e}")
        raise ValueError(f"Failed to fetch exchange rate for {from_currency}/{to_currency}: {e}")


def _fetch_rate_sync(from_currency: str, to_currency: str) -> Optional[Decimal]:
    """
    Synchronous version of the rate fetch function for use in ThreadPoolExecutor.

    Parameters:
        from_currency (str): Source currency code.
        to_currency (str): Target currency code.

    Returns:
        Optional[Decimal]: Exchange rate or None if unavailable.
    """
    try:
        # Create a new event loop in this thread
        import asyncio
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            result = new_loop.run_until_complete(_fetch_rate_async(from_currency, to_currency))
            return result
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)
    except Exception as e:
        logger.error(f"Error in sync rate fetch: {e}")
        return None


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
