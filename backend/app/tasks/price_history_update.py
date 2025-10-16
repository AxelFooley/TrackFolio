"""
Price history update tasks.

Maintains comprehensive price history database with optimized fetching.
"""
from celery import shared_task
from datetime import date, timedelta
from typing import List, Dict, Any
import logging
import time

from app.celery_app import celery_app
from app.services.price_history_manager import price_history_manager

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 300},
    retry_backoff=True,
    retry_backoff_max=1800,
    retry_jitter=True
)
def update_price_history_daily(self):
    """
    Daily task to ensure complete price history coverage for all symbols.

    This task runs once per day (typically in the early morning) to:
    1. Check for gaps in historical data
    2. Fetch missing data in bulk
    3. Update current day's prices
    4. Ensure all active symbols have complete coverage

    This replaces the old per-symbol price fetching approach with a more
    efficient bulk strategy.
    """
    logger.info("Starting daily price history update")

    try:
        # Get all active symbols
        symbols = list(price_history_manager.get_all_active_symbols())

        if not symbols:
            logger.info("No active symbols found for price history update")
            return {
                "status": "success",
                "message": "No active symbols found",
                "symbols_updated": 0,
                "total_added": 0,
                "total_updated": 0,
                "total_skipped": 0
            }

        logger.info(f"Updating price history for {len(symbols)} symbols")

        # Update today's prices for all symbols
        today = date.today()
        results = {}
        total_added = 0
        total_updated = 0
        total_skipped = 0
        failed_symbols = []

        for symbol in symbols:
            try:
                # Update today's price
                result = price_history_manager.fetch_and_store_complete_history(
                    symbol=symbol,
                    start_date=today,
                    force_update=True
                )

                results[symbol] = result
                total_added += result.get('added', 0)
                total_updated += result.get('updated', 0)
                total_skipped += result.get('skipped', 0)

                logger.debug(f"Updated {symbol}: {result}")

                # Rate limiting between symbols
                time.sleep(0.2)  # 200ms delay

            except Exception as e:
                logger.exception(f"Failed to update {symbol}: {e}")
                failed_symbols.append(symbol)
                results[symbol] = {
                    'added': 0,
                    'updated': 0,
                    'skipped': 0,
                    'error': str(e)
                }

        # Also ensure we have complete coverage (background task)
        try:
            # This will check for gaps in historical data and fill them
            # But run it with lower priority since today's prices are more important
            ensure_complete_coverage.apply_async(
                args=[symbols],
                countdown=3600  # 1 hour delay
            )
        except Exception as e:
            logger.warning(f"Failed to schedule coverage check: {e}")

        summary = {
            "status": "success",
            "message": f"Daily price history update completed for {len(symbols)} symbols",
            "symbols_updated": len(symbols) - len(failed_symbols),
            "total_added": total_added,
            "total_updated": total_updated,
            "total_skipped": total_skipped,
            "failed_symbols": failed_symbols,
            "failed_count": len(failed_symbols),
            "timestamp": date.today().isoformat()
        }

        logger.info(
            f"Daily price history update completed: "
            f"{total_added} added, {total_updated} updated, {total_skipped} skipped, "
            f"{len(failed_symbols)} failed"
        )

        return summary

    except Exception as e:
        logger.exception(f"Fatal error in daily price history update: {e}")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 600}
)
def ensure_complete_coverage(self, symbols: List[str] = None):
    """
    Background task to ensure complete price history coverage.

    Checks for gaps in historical data and fills them if needed.
    This runs as a background task with lower priority since it can
    take a long time for many symbols.

    Args:
        symbols: List of symbols to check (if None, checks all active symbols)
    """
    logger.info(f"Starting price coverage check for {len(symbols) if symbols else 'all'} symbols")

    try:
        if symbols is None:
            symbols = list(price_history_manager.get_all_active_symbols())

        results = price_history_manager.ensure_complete_coverage(symbols)

        # Count successful vs failed
        successful = sum(1 for complete in results.values() if complete)
        failed = len(results) - successful

        summary = {
            "status": "success",
            "message": f"Price coverage check completed for {len(symbols)} symbols",
            "symbols_checked": len(symbols),
            "successful": successful,
            "failed": failed,
            "timestamp": date.today().isoformat()
        }

        logger.info(f"Price coverage check completed: {successful} successful, {failed} failed")

        return summary

    except Exception as e:
        logger.exception(f"Error in price coverage check: {e}")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 1, 'countdown': 300}
)
def backfill_missing_history(self, symbols: List[str] = None):
    """
    Backfill missing historical data for specified symbols.

    This is useful when adding new symbols to the portfolio or when
    historical data gaps are discovered.

    Args:
        symbols: List of symbols to backfill (if None, backfills all active symbols)
    """
    logger.info(f"Starting backfill for {len(symbols) if symbols else 'all'} symbols")

    try:
        if symbols is None:
            symbols = list(price_history_manager.get_all_active_symbols())

        # Fetch 5 years of history for all symbols
        five_years_ago = date.today() - timedelta(days=5 * 365)
        results = price_history_manager.update_all_symbols_history(
            symbols=symbols,
            force_update=True
        )

        total_added = sum(r.get('added', 0) for r in results.values())
        total_updated = sum(r.get('updated', 0) for r in results.values())
        total_skipped = sum(r.get('skipped', 0) for r in results.values())

        summary = {
            "status": "success",
            "message": f"Backfill completed for {len(symbols)} symbols",
            "symbols_processed": len(symbols),
            "total_added": total_added,
            "total_updated": total_updated,
            "total_skipped": total_skipped,
            "timestamp": date.today().isoformat()
        }

        logger.info(f"Backfill completed: {total_added} added, {total_updated} updated, {total_skipped} skipped")

        return summary

    except Exception as e:
        logger.exception(f"Error in backfill task: {e}")
        raise


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 1, 'countdown': 60}
)
def refresh_current_prices(self, symbols: List[str] = None):
    """
    Refresh current day's prices for specified symbols.

    This is useful for manual price refresh or when markets close.

    Args:
        symbols: List of symbols to refresh (if None, refreshes all active symbols)
    """
    logger.info(f"Refreshing current prices for {len(symbols) if symbols else 'all'} symbols")

    try:
        if symbols is None:
            symbols = list(price_history_manager.get_all_active_symbols())

        today = date.today()
        results = {}
        total_updated = 0
        failed_symbols = []

        for symbol in symbols:
            try:
                result = price_history_manager.fetch_and_store_complete_history(
                    symbol=symbol,
                    start_date=today,
                    force_update=True
                )
                results[symbol] = result
                total_updated += result.get('added', 0) + result.get('updated', 0)

                # Rate limiting
                time.sleep(0.15)

            except Exception as e:
                logger.exception("Failed to refresh %s", symbol)
                failed_symbols.append(symbol)

        summary = {
            "status": "success",
            "message": f"Current prices refreshed for {len(symbols)} symbols",
            "symbols_processed": len(symbols) - len(failed_symbols),
            "total_updated": total_updated,
            "failed_symbols": failed_symbols,
            "failed_count": len(failed_symbols),
            "timestamp": date.today().isoformat()
        }

        logger.info(f"Current prices refresh completed: {total_updated} updated, {len(failed_symbols)} failed")

        return summary

    except Exception as e:
        logger.exception(f"Error in current prices refresh: {e}")
        raise