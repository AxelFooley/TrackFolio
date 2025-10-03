"""
Automatic backfill tasks.

Triggers historical price fetching and snapshot creation after transaction import.
"""
from celery import shared_task, chain
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import logging
import time

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import Transaction, PriceHistory
from app.services.price_fetcher import PriceFetcher
from app.services.ticker_mapper import TickerMapper

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 10},
    retry_backoff=True
)
def trigger_automatic_backfill(self):
    """
    Main orchestrator task that triggers after transaction import.

    Steps:
    1. Find earliest transaction date from Transaction table
    2. Set end_date to today
    3. Trigger backfill_historical_prices_for_all_tickers
    4. Chain to backfill_snapshots
    5. Chain to calculate_all_metrics

    Returns:
        dict: Summary of backfill operation
    """
    logger.info("Starting automatic backfill orchestration")

    db = SyncSessionLocal()

    try:
        # Find earliest transaction date
        result = db.execute(
            select(Transaction.operation_date)
            .order_by(Transaction.operation_date.asc())
            .limit(1)
        )
        earliest_txn = result.scalar_one_or_none()

        if not earliest_txn:
            logger.info("No transactions found. Skipping backfill.")
            return {
                "status": "skipped",
                "reason": "No transactions found"
            }

        start_date = earliest_txn
        end_date = date.today()

        logger.info(f"Backfilling data from {start_date} to {end_date}")

        # Convert dates to strings for serialization
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

        # Chain tasks: prices → snapshots → metrics
        from app.tasks.snapshots import backfill_snapshots
        from app.tasks.metric_calculation import calculate_all_metrics

        # Use Celery chain to sequence tasks
        workflow = chain(
            backfill_historical_prices_for_all_tickers.si(start_date_str, end_date_str),
            backfill_snapshots.si(start_date_str, end_date_str),
            calculate_all_metrics.si()
        )

        # Execute workflow asynchronously
        result = workflow.apply_async()

        logger.info(f"Backfill workflow triggered. Task chain ID: {result.id}")

        return {
            "status": "triggered",
            "start_date": start_date_str,
            "end_date": end_date_str,
            "workflow_id": result.id,
            "message": "Automatic backfill workflow started"
        }

    except Exception as e:
        logger.error(f"Error triggering automatic backfill: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 30},
    retry_backoff=True
)
def backfill_historical_prices_for_all_tickers(self, start_date: str, end_date: str):
    """
    Fetch historical prices for ALL unique tickers in transactions.

    Steps:
    1. Query Transaction table for unique tickers and their ISINs
    2. For each ticker:
       - Fetch historical price data from start_date to end_date
       - Use PriceFetcher.fetch_historical_prices_sync()
       - Save to PriceHistory table
       - Skip if price already exists (idempotency)
       - Add 0.5s delay between tickers (rate limiting)
    3. Log progress and errors

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD)

    Returns:
        dict: Summary with tickers_processed, prices_added, prices_skipped, failures
    """
    logger.info(f"Starting historical price backfill from {start_date} to {end_date}")

    db = SyncSessionLocal()
    price_fetcher = PriceFetcher()

    try:
        # Parse dates
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        # Get unique tickers with their ISINs
        result = db.execute(
            select(Transaction.ticker, Transaction.isin)
            .distinct()
        )
        ticker_isin_pairs = result.all()

        if not ticker_isin_pairs:
            logger.info("No tickers found in transactions.")
            return {
                "status": "success",
                "tickers_processed": 0,
                "prices_added": 0,
                "prices_skipped": 0,
                "failures": []
            }

        logger.info(f"Found {len(ticker_isin_pairs)} unique tickers to process")

        # Track results
        tickers_processed = 0
        prices_added = 0
        prices_skipped = 0
        failures = []

        for ticker, isin in ticker_isin_pairs:
            try:
                logger.info(f"Processing {ticker} (ISIN: {isin})...")

                # Fetch historical prices
                historical_prices = price_fetcher.fetch_historical_prices_sync(
                    ticker=ticker,
                    isin=isin,
                    start_date=start,
                    end_date=end
                )

                if not historical_prices:
                    logger.warning(f"No historical data available for {ticker}")
                    failures.append({
                        "ticker": ticker,
                        "reason": "No data available from API"
                    })
                    continue

                # Save each price record
                for price_data in historical_prices:
                    try:
                        # Check if price already exists (idempotency)
                        existing = db.execute(
                            select(PriceHistory)
                            .where(
                                PriceHistory.ticker == ticker,
                                PriceHistory.date == price_data["date"]
                            )
                        ).scalar_one_or_none()

                        if existing:
                            prices_skipped += 1
                            continue

                        # Create new price record
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
                        # Race condition: another process already added this price
                        db.rollback()
                        prices_skipped += 1
                        continue

                # Commit all prices for this ticker
                db.commit()

                tickers_processed += 1
                logger.info(
                    f"✓ {ticker}: Added {len(historical_prices)} price records "
                    f"(total added: {prices_added}, skipped: {prices_skipped})"
                )

                # Rate limiting: 0.5s delay between tickers
                time.sleep(0.5)

            except Exception as e:
                db.rollback()
                logger.error(f"Error processing {ticker}: {str(e)}")
                failures.append({
                    "ticker": ticker,
                    "reason": str(e)
                })

        # Summary
        summary = {
            "status": "completed",
            "start_date": start_date,
            "end_date": end_date,
            "tickers_processed": tickers_processed,
            "prices_added": prices_added,
            "prices_skipped": prices_skipped,
            "total_tickers": len(ticker_isin_pairs),
            "failures": failures
        }

        logger.info(
            f"Historical price backfill complete: "
            f"{tickers_processed}/{len(ticker_isin_pairs)} tickers processed, "
            f"{prices_added} prices added, {prices_skipped} skipped, "
            f"{len(failures)} failures"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in historical price backfill: {str(e)}")
        raise

    finally:
        db.close()
