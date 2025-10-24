"""
Price history update tasks.

Maintains comprehensive price history database with optimized fetching.
"""
from celery import shared_task
from datetime import date
import logging
import time

from app.database import SyncSessionLocal
from app.services.price_history_manager import price_history_manager
from app.services.system_state_manager import SystemStateManager

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

        # Update last price update timestamp
        try:
            db = SyncSessionLocal()
            SystemStateManager.update_price_last_update(db)
            db.close()
            logger.info("Updated price last update timestamp")
        except Exception as e:
            logger.error(f"Failed to update price last update timestamp: {e}")
            # Don't fail the entire task if timestamp update fails

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
