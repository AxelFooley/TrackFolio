"""
Crypto price update tasks.

Fetches latest crypto prices from Yahoo Finance API for all active crypto positions.
Runs every 5 minutes to keep crypto prices current.
"""
from celery import shared_task
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import logging
import time
import json

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import PriceHistory, CryptoTransaction, CryptoTransactionType
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
    Fetch and store latest prices for all crypto assets.

    This task is idempotent - it will not duplicate prices for the same date.
    Scheduled to run every 5 minutes.

    Returns:
        dict: Summary of prices updated, skipped, and failed
    """
    logger.info("Starting crypto price update task")

    db = SyncSessionLocal()

    try:
        # Get all unique crypto symbols from transactions
        result = db.execute(
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
        crypto_symbols = [row[0] for row in result.all()]

        if not crypto_symbols:
            logger.info("No crypto symbols found. Skipping crypto price update.")
            return {
                "status": "success",
                "updated": 0,
                "skipped": 0,
                "failed": 0,
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

        for symbol in crypto_symbols:
            try:
                # Check if price already exists for this date (idempotency)
                existing = db.execute(
                    select(PriceHistory)
                    .where(
                        PriceHistory.ticker == symbol,
                        PriceHistory.date == price_date
                    )
                ).scalar_one_or_none()

                if existing:
                    logger.debug(f"Price already exists for {symbol} on {price_date}. Skipping.")
                    skipped += 1
                    continue

                # Rate limiting: sleep 0.15s between requests to avoid Yahoo Finance rate limits
                time.sleep(0.15)

                # Fetch current price from Yahoo Finance
                price_fetcher = PriceFetcher()
                yahoo_symbol = f"{symbol}-USD"
                price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

                if not price_data or not price_data.get("current_price"):
                    logger.warning(f"No price data returned for {symbol}")
                    failed += 1
                    failed_symbols.append(symbol)
                    continue

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
                    date=price_date,
                    open=price_eur,  # Use same price for open/high/low for intraday
                    high=price_eur,
                    low=price_eur,
                    close=price_eur,
                    volume=0,  # Yahoo Finance real-time endpoint doesn't provide volume
                    source="yahoo"
                )

                db.add(price_record)
                db.commit()

                logger.info(
                    f"Updated crypto price for {symbol}: {price_eur} EUR on {price_date}"
                )
                updated += 1

            except IntegrityError as e:
                # Race condition: another process already inserted this price
                db.rollback()
                logger.debug(f"Price already exists for {symbol} (race condition)")
                skipped += 1

            except Exception as e:
                db.rollback()
                logger.error(f"Error fetching crypto price for {symbol}: {str(e)}")
                failed += 1
                failed_symbols.append(symbol)

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
            f"{failed} failed out of {len(crypto_symbols)} symbols"
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
def update_crypto_price_for_symbol(self, symbol: str, price_date: str = None):
    """
    Update price for a single crypto symbol.

    This is a utility task that can be called manually or from API endpoints.

    Args:
        symbol: Crypto symbol (e.g., 'BTC', 'ETH')
        price_date: Date string (YYYY-MM-DD). If None, uses today's date.

    Returns:
        dict: Price update result
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
        price_eur = price_usd * Decimal("0.92")  # Use fallback conversion rate

        # Create price record
        price_record = PriceHistory(
            ticker=symbol,
            date=target_date,
            open=price_eur,
            high=price_eur,
            low=price_eur,
            close=price_eur,
            volume=Decimal("0"),  # Yahoo Finance real-time endpoint doesn't provide volume
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
def backfill_crypto_prices(self, symbol: str, start_date: str, end_date: str = None):
    """
    Backfill historical prices for a crypto symbol.

    Args:
        symbol: Crypto symbol to backfill
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD). If None, uses today's date.

    Returns:
        dict: Summary of prices backfilled
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
            logger.warning(f"No historical crypto data for {symbol}")
            return {"status": "no_data", "symbol": symbol}

        # Save prices to database
        prices_added = 0
        prices_updated = 0
        prices_skipped = 0

        for price_data in historical_prices:
            try:
                # Convert to EUR if needed (Yahoo returns USD)
                price_usd = price_data["close"]
                price_eur = price_usd * Decimal("0.92")  # Use fallback conversion rate

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
                        existing.volume = Decimal("0")  # Yahoo Finance historical data doesn't include volume in this endpoint
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
                        volume=Decimal("0"),  # Yahoo Finance historical data doesn't include volume in this endpoint
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