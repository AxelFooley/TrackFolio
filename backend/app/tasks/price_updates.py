"""
Daily price update tasks.

Fetches latest prices from Yahoo Finance for all active positions.
"""
from celery import shared_task
from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import logging
import time

from app.database import SyncSessionLocal
from app.models import Position, PriceHistory
from app.services.price_fetcher import PriceFetcher
from app.services.system_state_manager import SystemStateManager

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

                # Fetch price for the exact target date
                # Rate limiting: sleep 0.5s between requests to avoid API throttling
                time.sleep(0.5)

                hist = price_fetcher.fetch_historical_prices_sync(
                    ticker=ticker,
                    isin=isin,
                    start_date=price_date,
                    end_date=price_date,
                )
                price_data = next((p for p in (hist or []) if p.get("date") == price_date), None)

                if not price_data or not price_data.get("close"):
                    logger.warning(f"No price data for {ticker} on {price_date} (ISIN: {isin})")
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

            except IntegrityError:
                # Race condition: another process already inserted this price
                db.rollback()
                logger.debug(f"Price already exists for {ticker} (race condition)")
                skipped += 1

            except Exception:
                db.rollback()
                logger.exception(f"Error fetching price for {ticker}")
                failed += 1
                failed_tickers.append(ticker)

        # Update last price update timestamp
        try:
            SystemStateManager.update_price_last_update(db)
            logger.info("Updated price last update timestamp")
        except Exception as e:
            logger.error(f"Failed to update price last update timestamp: {e}")
            # Don't fail the entire task if timestamp update fails

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
    Update the historical price for a single ticker on the specified date.

    If a price record for the target date already exists the task returns a skipped status.
    On success a new PriceHistory record is created and the returned dict includes the recorded price.

    Parameters:
        ticker (str): Ticker symbol to update.
        price_date (str, optional): Date string in `YYYY-MM-DD` format. If omitted, defaults to yesterday.

    Returns:
        dict: Result object with keys:
            - `status`: `"success"`, `"skipped"`, or `"failed"`.
            - `ticker`: the ticker symbol.
            - `price_date`: the target date as `YYYY-MM-DD`.
            - On success: `price` (float) with the recorded close price.
            - On skip or failure: `reason` (str) describing why the update was skipped or failed.
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

        # Fetch price for the exact target date
        hist = price_fetcher.fetch_historical_prices_sync(
            ticker=ticker,
            start_date=target_date,
            end_date=target_date,
        )
        price_data = next((p for p in (hist or []) if p.get("date") == target_date), None)

        if not price_data or not price_data.get("close"):
            logger.warning(f"No price data for {ticker} on {target_date}")
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
    Fetches historical daily prices for a ticker, upserts them into PriceHistory, and returns a summary of changes.

    Parameters:
        ticker (str): Ticker symbol to fetch.
        isin (str, optional): ISIN code to assist fetching when available.
        start_date (str, optional): Inclusive start date in YYYY-MM-DD format. Defaults to 365 days before today.
        end_date (str, optional): Inclusive end date in YYYY-MM-DD format. Defaults to today.

    Returns:
        dict: Summary with keys:
            - "status": "success" or "no_data".
            - "ticker": the ticker provided.
            - "start_date": string start date used.
            - "end_date": string end date used.
            - "prices_added": number of new records inserted.
            - "prices_updated": number of existing records updated when values differed.
            - "prices_skipped": number of records skipped (identical or due to race condition).
            - "total_fetched": number of price entries retrieved from the fetcher.

    Raises:
        Exception: Rolls back the transaction and re-raises on any unexpected error during fetch or persistence.
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