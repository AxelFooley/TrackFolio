"""
Backfill historical portfolio snapshots.

This script finds the earliest transaction date and creates daily snapshots
from that date to today using the backfill_snapshots Celery task.
"""
import sys
import os
from datetime import date
import logging

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SyncSessionLocal
from app.models import Transaction
from app.tasks.snapshots import backfill_snapshots
from sqlalchemy import select, func

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_earliest_transaction_date() -> date:
    """Find the earliest transaction date in the database."""
    db = SyncSessionLocal()

    try:
        result = db.execute(
            select(func.min(Transaction.operation_date))
        )
        earliest_date = result.scalar_one_or_none()

        if earliest_date is None:
            raise ValueError("No transactions found in the database")

        return earliest_date

    finally:
        db.close()


def main():
    """Main function to run the backfill."""
    logger.info("Starting portfolio snapshot backfill")
    logger.info("=" * 60)

    try:
        # Find earliest transaction date
        logger.info("Finding earliest transaction date...")
        start_date = find_earliest_transaction_date()
        logger.info(f"Earliest transaction date: {start_date}")

        # Set end date to today
        end_date = date.today()
        logger.info(f"End date (today): {end_date}")

        # Calculate number of days
        days = (end_date - start_date).days + 1
        logger.info(f"Will create snapshots for {days} days")
        logger.info("=" * 60)

        # Call the Celery task
        logger.info("Starting backfill task...")
        result = backfill_snapshots(
            start_date=str(start_date),
            end_date=str(end_date)
        )

        # Display results
        logger.info("=" * 60)
        logger.info("Backfill complete!")
        logger.info(f"Status: {result['status']}")
        logger.info(f"Created: {result['created']} snapshots")
        logger.info(f"Skipped: {result['skipped']} snapshots (already existed)")
        logger.info(f"Failed: {result['failed']} snapshots")
        logger.info(f"Total days processed: {result['total_days']}")
        logger.info("=" * 60)

        # Exit with appropriate code
        if result['failed'] > 0:
            logger.warning(f"{result['failed']} snapshots failed to create")
            sys.exit(1)
        else:
            logger.info("All snapshots created successfully!")
            sys.exit(0)

    except ValueError as e:
        logger.error(f"Error: {e}")
        logger.info("Make sure you have imported transactions before running this script.")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
