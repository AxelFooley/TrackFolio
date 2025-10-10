"""
Daily price update tasks.

Fetches latest prices from Yahoo Finance for all active positions.
"""
from celery import shared_task
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import logging
import time

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import Position, PriceHistory
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
def update_daily_prices(self):
    """
    Fetch and store latest prices for all active positions.

    This task is idempotent - it will not duplicate prices for the same date.
    Scheduled to run daily at 23:00 CET.

    Returns:
        dict: Summary of prices updated, skipped, and failed
    """
    logger.info("Starting daily price update task")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Get all active positions (quantity > 0)
        result = db.execute(
            select(Position)
            .where(Position.quantity > 0)
            .order_by(Position.current_ticker)
        )
        active_positions = result.scalars().all()

        if not active_positions:
            logger.info("No active positions found. Skipping price update.")
            return {
                "status": "success",
                "updated": 0,
                "skipped": 0,
                "failed": 0,
                "message": "No active positions"
            }

        logger.info(f"Found {len(active_positions)} active positions to update")

        # Get yesterday's date (since we run at 23:00, we want previous trading day's close)
        price_date = date.today() - timedelta(days=1)
        # Back off weekends (Saturday=5, Sunday=6)
        while price_date.weekday() >= 5:
            price_date -= timedelta(days=1)

        # Track results
        updated = 0
        skipped = 0
        failed = 0
        failed_tickers = []

        for position in active_positions:
            ticker = position.current_ticker  # Use current_ticker
            isin = position.isin

            try:
                # Check if price already exists for this date (idempotency)
                existing = db.execute(
                    select(PriceHistory)
                    .where(
                        PriceHistory.ticker == ticker,
                        PriceHistory.date == price_date
                    )
                ).scalar_one_or_none()

                if existing:
                    logger.debug(f"Price already exists for {ticker} on {price_date}. Skipping.")
                    skipped += 1
                    continue

                # Fetch latest price
                # Rate limiting: sleep 0.5s between requests to avoid API throttling
                time.sleep(0.5)

                price_data = price_fetcher.fetch_latest_price(ticker, isin)

                if not price_data or not price_data.get("close"):
                    logger.warning(f"No price data returned for {ticker} (ISIN: {isin})")
                    failed += 1
                    failed_tickers.append(ticker)
                    continue

                # Create price record
                price_record = PriceHistory(
                    ticker=ticker,
                    date=price_date,
                    open=price_data["open"],
                    high=price_data["high"],
                    low=price_data["low"],
                    close=price_data["close"],
                    volume=price_data["volume"],
                    source=price_data.get("source", "unknown")
                )

                db.add(price_record)
                db.commit()

                logger.info(
                    f"Updated price for {ticker}: {price_data['close']} on {price_date}"
                )
                updated += 1

            except IntegrityError as e:
                # Race condition: another process already inserted this price
                db.rollback()
                logger.debug(f"Price already exists for {ticker} (race condition)")
                skipped += 1

            except Exception:
                db.rollback()
                logger.exception(f"Error fetching price for {ticker}")
                failed += 1
                failed_tickers.append(ticker)

        # Summary
        summary = {
            "status": "success",
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "total_positions": len(active_positions),
            "price_date": str(price_date)
        }

        if failed_tickers:
            summary["failed_tickers"] = failed_tickers

        logger.info(
            f"Price update complete: {updated} updated, {skipped} skipped, "
            f"{failed} failed out of {len(active_positions)} positions"
        )

        return summary

    except Exception:
        logger.exception("Fatal error in price update task")
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
def update_price_for_ticker(self, ticker: str, price_date: str = None):
    """
    Update price for a single ticker.

    This is a utility task that can be called manually or from API endpoints.

    Args:
        ticker: Ticker symbol
        price_date: Date string (YYYY-MM-DD). If None, uses yesterday's date.

    Returns:
        dict: Price update result
    """
    logger.info(f"Updating price for {ticker}")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Parse date
        if price_date:
            target_date = date.fromisoformat(price_date)
        else:
            target_date = date.today() - timedelta(days=1)

        # Check if price already exists
        existing = db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.ticker == ticker,
                PriceHistory.date == target_date
            )
        ).scalar_one_or_none()

        if existing:
            logger.info(f"Price already exists for {ticker} on {target_date}")
            return {
                "status": "skipped",
                "ticker": ticker,
                "price_date": str(target_date),
                "reason": "Price already exists"
            }

        # Fetch price
        price_data = price_fetcher.fetch_latest_price(ticker)

        if not price_data or not price_data.get("close"):
            logger.warning(f"No price data returned for {ticker}")
            return {
                "status": "failed",
                "ticker": ticker,
                "price_date": str(target_date),
                "reason": "No price data available"
            }

        # Create price record
        price_record = PriceHistory(
            ticker=ticker,
            date=target_date,
            open=price_data["open"],
            high=price_data["high"],
            low=price_data["low"],
            close=price_data["close"],
            volume=price_data["volume"],
            source=price_data.get("source", "unknown")
        )

        db.add(price_record)
        db.commit()

        logger.info(f"Updated price for {ticker}: {price_data['close']}")

        return {
            "status": "success",
            "ticker": ticker,
            "price_date": str(target_date),
            "price": float(price_data["close"])
        }

    except IntegrityError:
        db.rollback()
        logger.debug(f"Price already exists for {ticker} (race condition)")
        return {
            "status": "skipped",
            "ticker": ticker,
            "price_date": str(target_date),
            "reason": "Price already exists"
        }

    except Exception:
        db.rollback()
        logger.exception(f"Error updating price for {ticker}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 10}
)
def fetch_prices_for_ticker(self, ticker: str, isin: str = None, start_date: str = None, end_date: str = None):
    """
    Fetch historical prices for a specific ticker.

    Used for benchmark price fetching.

    Args:
        ticker: Ticker symbol
        isin: Optional ISIN code
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)

    Returns:
        dict: Summary of prices fetched
    """
    logger.info(f"Starting historical price fetch for {ticker}")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Parse dates
        start = date.fromisoformat(start_date) if start_date else date.today() - timedelta(days=365)
        end = date.fromisoformat(end_date) if end_date else date.today()

        logger.info(f"Fetching prices for {ticker} from {start} to {end}")

        # Fetch historical prices
        historical_prices = price_fetcher.fetch_historical_prices_sync(
            ticker=ticker,
            isin=isin,
            start_date=start,
            end_date=end
        )

        if not historical_prices:
            logger.warning(f"No historical data for {ticker}")
            return {"status": "no_data", "ticker": ticker}

        # Save prices to database
        prices_added = 0
        prices_updated = 0
        prices_skipped = 0

        for price_data in historical_prices:
            try:
                # Check if price already exists
                existing = db.execute(
                    select(PriceHistory).where(
                        PriceHistory.ticker == ticker,
                        PriceHistory.date == price_data["date"]
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
                        existing.source = price_data.get("source", "yahoo")
                        prices_updated += 1
                    else:
                        prices_skipped += 1
                else:
                    # Add new price record
                    price_record = PriceHistory(
                        ticker=ticker,
                        date=price_data["date"],
                        open=price_data["open"],
                        high=price_data["high"],
                        low=price_data["low"],
                        close=price_data["close"],
                        volume=price_data["volume"],
                        source=price_data.get("source", "yahoo")
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
            "ticker": ticker,
            "start_date": str(start),
            "end_date": str(end),
            "prices_added": prices_added,
            "prices_updated": prices_updated,
            "prices_skipped": prices_skipped,
            "total_fetched": len(historical_prices)
        }

        logger.info(
            f"Historical price fetch complete for {ticker}: "
            f"{prices_added} added, {prices_updated} updated, {prices_skipped} skipped"
        )

        return summary

    except Exception:
        db.rollback()
        logger.exception(f"Error fetching historical prices for {ticker}")
        raise

    finally:
        db.close()
