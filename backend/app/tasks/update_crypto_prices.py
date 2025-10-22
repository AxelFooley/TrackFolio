"""
Crypto price update tasks.

Fetches latest crypto prices from Yahoo Finance API for all active crypto positions.
Runs every 5 minutes to keep crypto prices current.
"""
from celery import shared_task
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import logging
import time
import json

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import PriceHistory, CryptoTransaction, CryptoTransactionType, CryptoPortfolio
from app.services.price_fetcher import PriceFetcher
from app.services.currency_converter import get_exchange_rate

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def update_crypto_prices(self):
    """
    Fetch and store the latest EUR prices for all crypto assets referenced in transactions.
    
    This task is idempotent for a given date: it will not create duplicate PriceHistory entries for the same ticker and date. For each active crypto symbol it fetches a real-time USD price, converts it to EUR (using a dynamic USD→EUR rate with a fallback), and inserts a PriceHistory record. Records created use the same value for open/high/low/close and volume 0; symbols that already have a price for the target date are skipped.
    
    Returns:
        dict: Summary of the operation with keys:
            - status (str): "success" on normal completion.
            - updated (int): number of symbols for which a price record was added.
            - skipped (int): number of symbols skipped because a record already existed.
            - failed (int): number of symbols that failed to update.
            - total_symbols (int): total number of symbols processed.
            - price_date (str): ISO date string for the price entries.
            - failed_symbols (list, optional): list of symbol strings that failed (present only if any failed).
    """
    logger.info("Starting crypto price update task")

    db = SyncSessionLocal()

    try:
        # Get all unique crypto symbols from transactions
        symbols_result = db.execute(
            select(func.distinct(CryptoTransaction.symbol))
            .where(
                CryptoTransaction.transaction_type.in_([
                    CryptoTransactionType.BUY,
                    CryptoTransactionType.SELL,
                    CryptoTransactionType.TRANSFER_IN
                ])
            )
            .order_by(CryptoTransaction.symbol)
        )
        crypto_symbols = [row[0] for row in symbols_result.all()]

        # Get unique base currencies from active crypto portfolios
        currencies_result = db.execute(
            select(func.distinct(CryptoPortfolio.base_currency))
            .where(CryptoPortfolio.is_active == True)
        )
        base_currencies = [row[0] for row in currencies_result.all()]

        logger.info(f"Found {len(crypto_symbols)} crypto symbols and {len(base_currencies)} base currencies: {base_currencies}")

        if not crypto_symbols:
            logger.info("No crypto symbols found. Skipping crypto price update.")
            today = date.today()
            return {
                "status": "success",
                "updated": 0,
                "skipped": 0,
                "failed": 0,
                "total_symbols": 0,
                "price_date": str(today),
                "failed_symbols": [],
                "message": "No crypto symbols found"
            }

        logger.info(f"Found {len(crypto_symbols)} crypto symbols to update: {crypto_symbols}")

        # Get today's date
        price_date = date.today()

        # Track results
        updated = 0
        skipped = 0
        failed = 0
        failed_symbols = []

        # Fetch prices for each symbol in each base currency
        for symbol in crypto_symbols:
            for base_currency in base_currencies:
                try:
                    # base_currency is already a string from the database (e.g., "USD", "EUR")
                    currency_upper = base_currency.upper() if isinstance(base_currency, str) else base_currency.value.upper()
                    ticker_key = f"{symbol}-{currency_upper}"

                    # Check if price already exists for this date and currency (idempotency)
                    existing = db.execute(
                        select(PriceHistory)
                        .where(
                            PriceHistory.ticker == ticker_key,
                            PriceHistory.date == price_date
                        )
                    ).scalar_one_or_none()

                    if existing:
                        logger.debug(f"Price already exists for {ticker_key} on {price_date}. Skipping.")
                        skipped += 1
                        continue

                    # Rate limiting: sleep 0.15s between requests to avoid Yahoo Finance rate limits
                    time.sleep(0.15)

                    # Fetch current price from Yahoo Finance in the correct currency
                    price_fetcher = PriceFetcher()
                    yahoo_symbol = ticker_key
                    price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

                    if not price_data or not price_data.get("current_price"):
                        logger.warning(f"No price data returned for {ticker_key}")
                        failed += 1
                        failed_symbols.append(ticker_key)
                        continue

                    # Use price directly in the correct currency (no conversion needed)
                    price = price_data["current_price"]

                    # Create price record with currency-specific ticker
                    price_record = PriceHistory(
                        ticker=ticker_key,  # Store currency-specific ticker
                        date=price_date,
                        open=price,  # Use same price for open/high/low for intraday
                        high=price,
                        low=price,
                        close=price,
                        volume=0,  # Yahoo Finance real-time endpoint doesn't provide volume
                        source="yahoo"
                    )

                    db.add(price_record)
                    db.commit()

                    logger.info(
                        f"Updated crypto price for {ticker_key}: {price} {currency_upper} on {price_date}"
                    )
                    updated += 1

                except IntegrityError as e:
                    # Race condition: another process already inserted this price
                    db.rollback()
                    currency_upper = base_currency.upper() if isinstance(base_currency, str) else base_currency.value.upper()
                    logger.debug(f"Price already exists for {symbol}-{currency_upper} (race condition)")
                    skipped += 1

                except Exception as e:
                    db.rollback()
                    currency_upper = base_currency.upper() if isinstance(base_currency, str) else base_currency.value.upper()
                    logger.error(f"Error fetching crypto price for {symbol}-{currency_upper}: {str(e)}")
                    failed += 1
                    currency_upper = base_currency.upper() if isinstance(base_currency, str) else base_currency.value.upper()
                    failed_symbols.append(f"{symbol}-{currency_upper}")

        # Summary
        summary = {
            "status": "success",
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "total_symbols": len(crypto_symbols),
            "price_date": str(price_date)
        }

        if failed_symbols:
            summary["failed_symbols"] = failed_symbols

        logger.info(
            f"Crypto price update complete: {updated} updated, {skipped} skipped, "
            f"{failed} failed out of {len(crypto_symbols)} symbols in {len(base_currencies)} currencies"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in crypto price update task: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def update_crypto_price_for_symbol(self, symbol: str, price_date: Optional[str] = None):
    """
    Update and store the price for a single cryptocurrency symbol for a given date.
    
    If a PriceHistory entry for the symbol and date already exists, the operation is skipped.
    Otherwise the function fetches the current price (USD), converts it to EUR using a fallback rate,
    creates a PriceHistory record, and returns a result describing the outcome.
    
    Parameters:
        symbol (str): Crypto symbol (e.g., "BTC", "ETH").
        price_date (str | None): ISO date string "YYYY-MM-DD". If None, uses today's date.
    
    Returns:
        dict: Result payload with keys:
            - status (str): "success", "skipped", or "failed".
            - symbol (str): The provided symbol.
            - price_date (str): The target date as "YYYY-MM-DD".
            - price (float, optional): EUR price when status is "success".
            - currency (str, optional): "EUR" when status is "success".
            - reason (str, optional): Explanation when status is "skipped" or "failed".
    """
    logger.info(f"Updating crypto price for {symbol}")

    db = SyncSessionLocal()

    try:
        # Parse date
        if price_date:
            target_date = date.fromisoformat(price_date)
        else:
            target_date = date.today()

        # Check if price already exists
        existing = db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.ticker == symbol,
                PriceHistory.date == target_date
            )
        ).scalar_one_or_none()

        if existing:
            logger.info(f"Price already exists for {symbol} on {target_date}")
            return {
                "status": "skipped",
                "symbol": symbol,
                "price_date": str(target_date),
                "reason": "Price already exists"
            }

        # Fetch price from Yahoo Finance
        price_fetcher = PriceFetcher()
        yahoo_symbol = f"{symbol}-USD"
        price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

        if not price_data or not price_data.get("current_price"):
            logger.warning(f"No price data returned for {symbol}")
            return {
                "status": "failed",
                "symbol": symbol,
                "price_date": str(target_date),
                "reason": "No price data available"
            }

        # Convert to EUR if needed (Yahoo returns USD)
        price_usd = price_data["current_price"]
        # Convert to EUR using dynamic exchange rate
        try:
            usd_to_eur_rate = get_exchange_rate("USD", "EUR")
            price_eur = price_usd * usd_to_eur_rate
        except Exception as e:
            logger.warning(f"Failed to fetch USD→EUR rate for {symbol}: {e}. Using fallback rate.")
            price_eur = price_usd * Decimal("0.92")  # Fallback conversion rate

        # Create price record
        price_record = PriceHistory(
            ticker=symbol,
            date=target_date,
            open=price_eur,
            high=price_eur,
            low=price_eur,
            close=price_eur,
            volume=int(price_data.get("volume", 0)),
            source="yahoo"
        )

        db.add(price_record)
        db.commit()

        logger.info(f"Updated crypto price for {symbol}: {price_eur} EUR")

        return {
            "status": "success",
            "symbol": symbol,
            "price_date": str(target_date),
            "price": float(price_eur),
            "currency": "EUR"
        }

    except IntegrityError:
        db.rollback()
        logger.debug(f"Price already exists for {symbol} (race condition)")
        return {
            "status": "skipped",
            "symbol": symbol,
            "price_date": str(target_date),
            "reason": "Price already exists"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error updating crypto price for {symbol}: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 60}
)
def backfill_crypto_prices(self, symbol: str, start_date: str, end_date: Optional[str] = None):
    """
    Backfill historical EUR-denominated prices for a crypto symbol over a date range.
    
    Fetches historical USD prices for `symbol` from Yahoo Finance, converts close prices to EUR using a fallback rate, and creates or updates PriceHistory records for each date in the range.
    
    Parameters:
        symbol (str): Crypto symbol (e.g., "BTC") to backfill.
        start_date (str): Inclusive start date in "YYYY-MM-DD" format.
        end_date (str, optional): Inclusive end date in "YYYY-MM-DD" format; if None, uses today's date.
    
    Returns:
        dict: Summary of the backfill operation containing:
            - status (str): "success" or "no_data".
            - symbol (str): The input symbol.
            - start_date (str): Start date used.
            - end_date (str): End date used.
            - prices_added (int): Number of new records created.
            - prices_updated (int): Number of existing records updated.
            - prices_skipped (int): Number of records skipped (unchanged or due to race conditions).
            - total_fetched (int): Number of price points fetched from the provider.
    """
    logger.info(f"Starting crypto price backfill for {symbol}")

    db = SyncSessionLocal()

    try:
        # Parse dates
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else date.today()

        logger.info(f"Backfilling crypto prices for {symbol} from {start} to {end}")

        # Fetch historical prices from Yahoo Finance
        price_fetcher = PriceFetcher()
        yahoo_symbol = f"{symbol}-USD"
        historical_prices = price_fetcher.fetch_historical_prices_sync(
            ticker=yahoo_symbol,
            start_date=start,
            end_date=end
        )

        if not historical_prices:
            logger.warning("No historical crypto data for %s", symbol)
            return {
                "status": "no_data",
                "symbol": symbol,
                "start_date": str(start),
                "end_date": str(end),
                "prices_added": 0,
                "prices_updated": 0,
                "prices_skipped": 0,
                "total_fetched": 0
            }
        # Fetch USD→EUR rate once for all historical prices
        try:
            usd_to_eur_rate = get_exchange_rate("USD", "EUR")
            logger.info(f"Using dynamic USD→EUR rate: {usd_to_eur_rate}")
        except Exception as e:
            logger.warning(f"Failed to fetch USD→EUR rate for backfill: {e}. Using fallback rate.")
            usd_to_eur_rate = Decimal("0.92")

        # Save prices to database
        prices_added = 0
        prices_updated = 0
        prices_skipped = 0

        for price_data in historical_prices:
            try:
                # Convert to EUR if needed (Yahoo returns USD)
                price_usd = price_data["close"]
                price_eur = price_usd * usd_to_eur_rate

                # Check if price already exists
                existing = db.execute(
                    select(PriceHistory).where(
                        PriceHistory.ticker == symbol,
                        PriceHistory.date == price_data["date"]
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing price if values differ
                    if existing.close != price_eur:
                        existing.open = price_eur
                        existing.high = price_eur
                        existing.low = price_eur
                        existing.close = price_eur
                        existing.volume = 0  # Yahoo Finance historical data doesn't include volume in this endpoint
                        existing.source = "yahoo"
                        prices_updated += 1
                    else:
                        prices_skipped += 1
                else:
                    # Add new price record
                    price_record = PriceHistory(
                        ticker=symbol,
                        date=price_data["date"],
                        open=price_eur,
                        high=price_eur,
                        low=price_eur,
                        close=price_eur,
                        volume=0,  # Yahoo Finance historical data doesn't include volume in this endpoint
                        source="yahoo"
                    )
                    db.add(price_record)
                    prices_added += 1

            except IntegrityError:
                # Race condition - price was inserted by another process
                db.rollback()
                prices_skipped += 1
                continue

        # Commit all changes
        db.commit()

        summary = {
            "status": "success",
            "symbol": symbol,
            "start_date": str(start),
            "end_date": str(end),
            "prices_added": prices_added,
            "prices_updated": prices_updated,
            "prices_skipped": prices_skipped,
            "total_fetched": len(historical_prices)
        }

        logger.info(
            f"Crypto price backfill complete for {symbol}: "
            f"{prices_added} added, {prices_updated} updated, {prices_skipped} skipped"
        )

        return summary

    except Exception as e:
        db.rollback()
        logger.error(f"Error backfilling crypto prices for {symbol}: {str(e)}")
        raise

    finally:
        db.close()