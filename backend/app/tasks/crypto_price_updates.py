"""
Crypto price update tasks for paper wallet integration.

Fetches cryptocurrency prices from CoinGecko API for all crypto assets
held in paper portfolios. Runs every 5 minutes due to crypto volatility.
"""
from celery import shared_task
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
import logging
import time
import json
from typing import Dict, List, Optional

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import PriceHistory
from app.models.crypto_paper import CryptoPaperTransaction
from app.services.price_fetcher import PriceFetcher

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def update_crypto_prices(self):
    """
    Fetch and store latest prices for all crypto assets in paper portfolios.

    This task is idempotent - it will not duplicate prices for the same date.
    Scheduled to run every 5 minutes due to crypto volatility.

    Returns:
        dict: Summary of prices updated, skipped, and failed
    """
    logger.info("Starting crypto price update task")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Get all unique crypto symbols with active holdings from paper portfolios
        # Only include symbols where total quantity > 0 (active holdings)
        from sqlalchemy import case

        result = db.execute(
            select(CryptoPaperTransaction.symbol)
            .group_by(CryptoPaperTransaction.symbol)
            .having(
                func.sum(
                    case(
                        (CryptoPaperTransaction.transaction_type == 'buy', CryptoPaperTransaction.quantity),
                        (CryptoPaperTransaction.transaction_type == 'transfer_in', CryptoPaperTransaction.quantity),
                        (CryptoPaperTransaction.transaction_type == 'sell', -CryptoPaperTransaction.quantity),
                        (CryptoPaperTransaction.transaction_type == 'transfer_out', -CryptoPaperTransaction.quantity),
                        else_=0
                    )
                ) > 0
            )
        )
        crypto_symbols = [row[0] for row in result.all()]

        if not crypto_symbols:
            logger.info("No crypto assets with active holdings found. Skipping crypto price update.")
            return {
                "status": "success",
                "updated": 0,
                "skipped": 0,
                "failed": 0,
                "message": "No active crypto holdings"
            }

        logger.info(f"Found {len(crypto_symbols)} crypto symbols to update: {crypto_symbols}")

        # Use today's date for crypto prices (they trade 24/7)
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
                        PriceHistory.date == price_date,
                        PriceHistory.source == 'coingecko'
                    )
                ).scalar_one_or_none()

                if existing:
                    logger.debug(f"Price already exists for {symbol} on {price_date}. Skipping.")
                    skipped += 1
                    continue

                # Fetch current crypto price using CoinGecko
                # Rate limiting: sleep 1.5s between requests (CoinGecko free tier limit)
                time.sleep(1.5)

                price_data = price_fetcher.fetch_latest_price(symbol)

                if not price_data or not price_data.get("close"):
                    logger.warning(f"No price data returned for {symbol}")
                    failed += 1
                    failed_symbols.append(symbol)
                    continue

                # Create price record with source as coingecko
                price_record = PriceHistory(
                    ticker=symbol,
                    date=price_date,
                    open=price_data["open"],
                    high=price_data["high"],
                    low=price_data["low"],
                    close=price_data["close"],
                    volume=price_data["volume"],
                    source="coingecko"
                )

                db.add(price_record)
                db.commit()

                logger.info(
                    f"Updated crypto price for {symbol}: {price_data['close']} on {price_date}"
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
            "price_date": str(price_date),
            "source": "coingecko"
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
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def update_crypto_price_for_symbol(self, symbol: str, price_date: str = None, currency: str = "eur"):
    """
    Update price for a single crypto symbol.

    This is a utility task that can be called manually or from API endpoints.

    Args:
        symbol: Crypto symbol (e.g., BTC, ETH)
        price_date: Date string (YYYY-MM-DD). If None, uses today's date.
        currency: Target currency (eur or usd, default: eur)

    Returns:
        dict: Price update result
    """
    logger.info(f"Updating crypto price for {symbol}")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

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
                PriceHistory.date == target_date,
                PriceHistory.source == 'coingecko'
            )
        ).scalar_one_or_none()

        if existing:
            logger.info(f"Price already exists for {symbol} on {target_date}")
            return {
                "status": "skipped",
                "symbol": symbol,
                "price_date": str(target_date),
                "currency": currency,
                "reason": "Price already exists"
            }

        # Fetch price using CoinGecko
        price_data = price_fetcher.fetch_latest_price(symbol)

        if not price_data or not price_data.get("close"):
            logger.warning(f"No price data returned for {symbol}")
            return {
                "status": "failed",
                "symbol": symbol,
                "price_date": str(target_date),
                "currency": currency,
                "reason": "No price data available"
            }

        # Create price record
        price_record = PriceHistory(
            ticker=symbol,
            date=target_date,
            open=price_data["open"],
            high=price_data["high"],
            low=price_data["low"],
            close=price_data["close"],
            volume=price_data["volume"],
            source="coingecko"
        )

        db.add(price_record)
        db.commit()

        logger.info(f"Updated crypto price for {symbol}: {price_data['close']}")

        return {
            "status": "success",
            "symbol": symbol,
            "price_date": str(target_date),
            "currency": currency,
            "price": float(price_data["close"]),
            "volume": price_data.get("volume", 0)
        }

    except IntegrityError:
        db.rollback()
        logger.debug(f"Price already exists for {symbol} (race condition)")
        return {
            "status": "skipped",
            "symbol": symbol,
            "price_date": str(target_date),
            "currency": currency,
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
    retry_kwargs={'max_retries': 2, 'countdown': 10}
)
def backfill_crypto_prices(self, symbol: str, days: int = 30, currency: str = "eur"):
    """
    Backfill historical crypto prices for a symbol.

    Fetches historical data from CoinGecko for the specified number of days.

    Args:
        symbol: Crypto symbol (e.g., BTC, ETH)
        days: Number of days to backfill (default: 30)
        currency: Target currency (eur or usd, default: eur)

    Returns:
        dict: Summary of backfill results
    """
    logger.info(f"Starting crypto price backfill for {symbol} ({days} days)")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Calculate date range
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        logger.info(f"Fetching crypto prices for {symbol} from {start_date} to {end_date}")

        # Fetch historical prices using PriceFetcher
        historical_prices = price_fetcher.fetch_historical_prices_sync(
            ticker=symbol,
            start_date=start_date,
            end_date=end_date
        )

        # Filter to only crypto prices
        crypto_prices = [p for p in historical_prices if p.get("source") == "coingecko"]

        if not crypto_prices:
            logger.warning(f"No historical crypto data for {symbol}")
            return {
                "status": "no_data",
                "symbol": symbol,
                "start_date": str(start_date),
                "end_date": str(end_date)
            }

        # Save prices to database
        prices_added = 0
        prices_updated = 0
        prices_skipped = 0

        for price_data in crypto_prices:
            try:
                # Check if price already exists
                existing = db.execute(
                    select(PriceHistory).where(
                        PriceHistory.ticker == symbol,
                        PriceHistory.date == price_data["date"],
                        PriceHistory.source == 'coingecko'
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing price if values differ
                    if (existing.close != price_data["close"] or
                        existing.open != price_data["open"] or
                        existing.high != price_data["high"] or
                        existing.low != price_data["low"]):
                        existing.open = price_data["open"]
                        existing.high = price_data["high"]
                        existing.low = price_data["low"]
                        existing.close = price_data["close"]
                        existing.volume = price_data["volume"]
                        prices_updated += 1
                    else:
                        prices_skipped += 1
                else:
                    # Add new price record
                    price_record = PriceHistory(
                        ticker=symbol,
                        date=price_data["date"],
                        open=price_data["open"],
                        high=price_data["high"],
                        low=price_data["low"],
                        close=price_data["close"],
                        volume=price_data["volume"],
                        source="coingecko"
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
            "start_date": str(start_date),
            "end_date": str(end_date),
            "currency": currency,
            "prices_added": prices_added,
            "prices_updated": prices_updated,
            "prices_skipped": prices_skipped,
            "total_fetched": len(crypto_prices)
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


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 1, 'countdown': 30}
)
def refresh_crypto_cache(self):
    """
    Refresh the most recent crypto prices for all active holdings.

    This task forces an update of today's prices even if they already exist,
    ensuring the latest prices are available throughout the trading day.

    Returns:
        dict: Summary of cache refresh results
    """
    logger.info("Starting crypto cache refresh task")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Get all unique crypto symbols with active holdings
        from sqlalchemy import case

        result = db.execute(
            select(CryptoPaperTransaction.symbol)
            .group_by(CryptoPaperTransaction.symbol)
            .having(
                func.sum(
                    case(
                        (CryptoPaperTransaction.transaction_type == 'buy', CryptoPaperTransaction.quantity),
                        (CryptoPaperTransaction.transaction_type == 'transfer_in', CryptoPaperTransaction.quantity),
                        (CryptoPaperTransaction.transaction_type == 'sell', -CryptoPaperTransaction.quantity),
                        (CryptoPaperTransaction.transaction_type == 'transfer_out', -CryptoPaperTransaction.quantity),
                        else_=0
                    )
                ) > 0
            )
        )
        crypto_symbols = [row[0] for row in result.all()]

        if not crypto_symbols:
            logger.info("No crypto assets with active holdings found. Skipping cache refresh.")
            return {
                "status": "success",
                "updated": 0,
                "failed": 0,
                "message": "No active crypto holdings"
            }

        logger.info(f"Refreshing cache for {len(crypto_symbols)} crypto symbols")

        # Use today's date
        price_date = date.today()

        # Track results
        updated = 0
        failed = 0
        failed_symbols = []

        for symbol in crypto_symbols:
            try:
                # Rate limiting
                time.sleep(1.5)

                # Fetch current price
                price_data = price_fetcher.fetch_latest_price(symbol)

                if not price_data or not price_data.get("close"):
                    logger.warning(f"No price data returned for {symbol}")
                    failed += 1
                    failed_symbols.append(symbol)
                    continue

                # Upsert price (update if exists, insert if not)
                existing = db.execute(
                    select(PriceHistory)
                    .where(
                        PriceHistory.ticker == symbol,
                        PriceHistory.date == price_date,
                        PriceHistory.source == 'coingecko'
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing record
                    existing.open = price_data["open"]
                    existing.high = price_data["high"]
                    existing.low = price_data["low"]
                    existing.close = price_data["close"]
                    existing.volume = price_data["volume"]
                    logger.debug(f"Updated existing price for {symbol}")
                else:
                    # Insert new record
                    price_record = PriceHistory(
                        ticker=symbol,
                        date=price_date,
                        open=price_data["open"],
                        high=price_data["high"],
                        low=price_data["low"],
                        close=price_data["close"],
                        volume=price_data["volume"],
                        source="coingecko"
                    )
                    db.add(price_record)
                    logger.debug(f"Inserted new price for {symbol}")

                db.commit()
                updated += 1

            except Exception as e:
                db.rollback()
                logger.error(f"Error refreshing crypto price for {symbol}: {str(e)}")
                failed += 1
                failed_symbols.append(symbol)

        # Summary
        summary = {
            "status": "success",
            "updated": updated,
            "failed": failed,
            "total_symbols": len(crypto_symbols),
            "price_date": str(price_date),
            "source": "coingecko"
        }

        if failed_symbols:
            summary["failed_symbols"] = failed_symbols

        logger.info(
            f"Crypto cache refresh complete: {updated} updated, {failed} failed "
            f"out of {len(crypto_symbols)} symbols"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in crypto cache refresh task: {str(e)}")
        raise

    finally:
        db.close()