"""
Currency conversion service.

Provides currency exchange rate fetching for converting between different currencies.
This module delegates to FXRateService for actual rate fetching and caching, while
maintaining a backward-compatible synchronous API for existing code.

NOTE: This module is deprecated in favor of FXRateService. Use FXRateService directly
for new code, as it provides async/await support, better caching, and more features.
This module is maintained for backward compatibility only.
"""
from decimal import Decimal
from typing import Optional
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.services.fx_rate_service import get_fx_service

logger = logging.getLogger(__name__)

# Thread pool executor for running sync functions in async contexts
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="currency_converter")


def get_exchange_rate(from_currency: str, to_currency: str) -> Decimal:
    """
    Get the current exchange rate from one currency to another.

    This function fetches the current exchange rate, converting from_currency to to_currency.
    For example, get_exchange_rate("USD", "EUR") returns how many EUR equal 1 USD.

    This is a synchronous wrapper around FXRateService for backward compatibility.

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

    Deprecated:
        Use FXRateService.get_current_rate() directly for new code with async/await support.
    """
    # Handle same currency conversion
    if from_currency == to_currency:
        logger.debug(f"Same currency conversion requested: {from_currency}")
        return Decimal("1.0")

    try:
        logger.debug(f"Fetching exchange rate: {from_currency} -> {to_currency}")

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

        logger.debug(f"Exchange rate {from_currency}/{to_currency}: {rate}")
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
    Internal async helper to fetch exchange rate from FXRateService.

    Delegates to the shared FXRateService instance which handles caching,
    fallback rates, and retry logic.

    Parameters:
        from_currency (str): Source currency code.
        to_currency (str): Target currency code.

    Returns:
        Optional[Decimal]: Exchange rate or None if unavailable.
    """
    try:
        service = get_fx_service()
        # Use fallback=False to raise exception on failure rather than returning fallback
        # This maintains backward compatibility with the original get_exchange_rate behavior
        rate = await service.get_current_rate(
            from_currency, to_currency, use_fallback=False
        )
        return rate
    except Exception as e:
        logger.debug(f"Error fetching rate via FXRateService: {e}")
        return None


def get_exchange_rate_with_fallback(
    from_currency: str,
    to_currency: str,
    fallback_rate: Optional[Decimal] = None
) -> Decimal:
    """
    Get exchange rate with a fallback value if the primary fetch fails.

    This is useful for non-critical operations where having a reasonable estimate
    is better than failing entirely. This function delegates to FXRateService which
    provides comprehensive fallback rate handling.

    Parameters:
        from_currency (str): Source currency code.
        to_currency (str): Target currency code.
        fallback_rate (Optional[Decimal]): Rate to use if fetch fails.
            If None, uses FXRateService's hardcoded fallback rates.

    Returns:
        Decimal: Exchange rate (either fetched or fallback).

    Example:
        >>> # Try to fetch, but use 0.92 if it fails
        >>> rate = get_exchange_rate_with_fallback("USD", "EUR", Decimal("0.92"))

    Deprecated:
        Use FXRateService.get_current_rate() directly with use_fallback=True for new code.
    """
    try:
        return get_exchange_rate(from_currency, to_currency)
    except Exception as e:
        logger.warning(
            f"Failed to fetch exchange rate {from_currency}/{to_currency}: {e}. "
            f"Using fallback rate."
        )

        # Use provided fallback or delegate to FXRateService
        if fallback_rate is not None:
            logger.info(f"Using provided fallback rate for {from_currency}/{to_currency}: {fallback_rate}")
            return fallback_rate

        # Delegate to FXRateService for its comprehensive fallback rates
        try:
            # Run async call to get service's fallback rate
            try:
                loop = asyncio.get_running_loop()
                future = _executor.submit(_get_service_fallback_sync, from_currency, to_currency)
                fallback = future.result(timeout=5)
            except RuntimeError:
                fallback = _get_service_fallback_sync(from_currency, to_currency)

            if fallback is not None:
                logger.info(f"Using FXRateService fallback rate for {from_currency}/{to_currency}: {fallback}")
                return fallback
        except Exception as e2:
            logger.debug(f"Could not get FXRateService fallback: {e2}")

        # If no fallback available, raise error
        raise ValueError(
            f"No fallback rate available for {from_currency}/{to_currency}. "
            f"Please provide a fallback_rate parameter."
        )


def _get_service_fallback_sync(from_currency: str, to_currency: str) -> Optional[Decimal]:
    """
    Get fallback rate from FXRateService in sync context.

    Parameters:
        from_currency (str): Source currency code.
        to_currency (str): Target currency code.

    Returns:
        Optional[Decimal]: Fallback rate or None if unavailable.
    """
    try:
        import asyncio
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            service = get_fx_service()
            # Use fallback=True to get the fallback rate
            result = new_loop.run_until_complete(
                service.get_current_rate(from_currency, to_currency, use_fallback=True)
            )
            return result
        finally:
            new_loop.close()
            asyncio.set_event_loop(None)
    except Exception as e:
        logger.debug(f"Error getting service fallback: {e}")
        return None
