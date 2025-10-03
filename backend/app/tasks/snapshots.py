"""
Daily portfolio snapshot tasks.

Creates daily snapshots of portfolio value for historical tracking and charts.
"""
from celery import shared_task
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import logging

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import Position, PriceHistory, PortfolioSnapshot, Transaction, TransactionType
from app.services.price_fetcher import PriceFetcher
from sqlalchemy import func

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5},
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True
)
def create_daily_snapshot(self, snapshot_date: str = None):
    """
    Create daily portfolio snapshot.

    This task is idempotent - it will not create duplicate snapshots for the same date.
    Scheduled to run daily at 23:30 CET (after prices and metrics are updated).

    Args:
        snapshot_date: Date string (YYYY-MM-DD). If None, uses today's date.

    Returns:
        dict: Snapshot summary
    """
    logger.info("Starting daily snapshot task")

    db = SyncSessionLocal()

    try:
        # Parse date
        if snapshot_date:
            target_date = date.fromisoformat(snapshot_date)
        else:
            target_date = date.today()

        # Check if snapshot already exists (idempotency)
        existing = db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.snapshot_date == target_date)
        ).scalar_one_or_none()

        if existing:
            logger.info(f"Snapshot already exists for {target_date}. Skipping.")
            return {
                "status": "skipped",
                "snapshot_date": str(target_date),
                "reason": "Snapshot already exists",
                "total_value": float(existing.total_value),
                "total_cost_basis": float(existing.total_cost_basis)
            }

        # CRITICAL: Reconstruct positions from transaction history up to snapshot_date
        # Query all transactions up to and including the snapshot date
        transactions_result = db.execute(
            select(Transaction)
            .where(Transaction.operation_date <= target_date)
            .order_by(Transaction.operation_date)
        )
        transactions = transactions_result.scalars().all()

        if not transactions:
            logger.warning(f"No transactions found up to {target_date}. Creating zero-value snapshot.")
            snapshot = PortfolioSnapshot(
                snapshot_date=target_date,
                total_value=Decimal("0"),
                total_cost_basis=Decimal("0"),
                currency="EUR"
            )
            db.add(snapshot)
            db.commit()

            return {
                "status": "success",
                "snapshot_date": str(target_date),
                "total_value": 0,
                "total_cost_basis": 0,
                "num_positions": 0,
                "message": "No transactions up to this date"
            }

        # Reconstruct positions from transactions
        # Group by ISIN and calculate net quantity and cost basis
        positions_by_isin = {}

        for txn in transactions:
            isin = txn.isin

            if isin not in positions_by_isin:
                positions_by_isin[isin] = {
                    "isin": isin,
                    "ticker": txn.ticker,  # Use ticker from transaction (will be updated below)
                    "description": txn.description,
                    "quantity": Decimal("0"),
                    "total_cost": Decimal("0"),  # Total amount invested
                }

            # Calculate quantity change
            if txn.transaction_type == TransactionType.BUY:
                positions_by_isin[isin]["quantity"] += txn.quantity
                # Cost basis includes amount + fees
                positions_by_isin[isin]["total_cost"] += abs(txn.amount_eur) + txn.fees
            else:  # SELL
                positions_by_isin[isin]["quantity"] -= txn.quantity
                # Reduce cost basis proportionally when selling
                # For simplicity in snapshot, we'll track net investment
                positions_by_isin[isin]["total_cost"] -= abs(txn.amount_eur) - txn.fees

        # Filter out positions with zero or negative quantity
        historical_positions = {
            isin: data for isin, data in positions_by_isin.items()
            if data["quantity"] > 0
        }

        if not historical_positions:
            logger.warning(f"No active positions for {target_date}. Creating zero-value snapshot.")
            snapshot = PortfolioSnapshot(
                snapshot_date=target_date,
                total_value=Decimal("0"),
                total_cost_basis=Decimal("0"),
                currency="EUR"
            )
            db.add(snapshot)
            db.commit()

            return {
                "status": "success",
                "snapshot_date": str(target_date),
                "total_value": 0,
                "total_cost_basis": 0,
                "num_positions": 0,
                "message": "No active positions on this date"
            }

        logger.info(f"Reconstructed {len(historical_positions)} positions for {target_date}")

        # Now get current_ticker from Position table for price lookups
        # Map ISIN to current ticker (handles ticker changes/splits)
        isin_to_current_ticker = {}
        for isin in historical_positions.keys():
            position_record = db.execute(
                select(Position).where(Position.isin == isin)
            ).scalar_one_or_none()

            if position_record:
                isin_to_current_ticker[isin] = position_record.current_ticker
            else:
                # Fallback to transaction ticker if no Position record
                isin_to_current_ticker[isin] = historical_positions[isin]["ticker"]

        # Calculate portfolio totals using historical positions and historical prices
        total_value = Decimal("0")
        total_cost_basis = Decimal("0")
        missing_prices = []

        for isin, position_data in historical_positions.items():
            ticker = isin_to_current_ticker.get(isin, position_data["ticker"])
            quantity = position_data["quantity"]
            cost = position_data["total_cost"]

            # Get historical price for this date (or closest earlier date)
            price_record = db.execute(
                select(PriceHistory)
                .where(PriceHistory.ticker == ticker)
                .where(PriceHistory.date <= target_date)
                .order_by(PriceHistory.date.desc())
                .limit(1)
            ).scalar_one_or_none()

            if price_record:
                historical_price = price_record.close
            else:
                # No historical price available
                logger.warning(
                    f"No price history for {ticker} (ISIN: {isin}) up to {target_date}. "
                    f"Skipping from snapshot."
                )
                missing_prices.append(ticker)
                continue

            # Calculate position value and cost basis
            position_value = quantity * historical_price
            position_cost_basis = cost

            total_value += position_value
            total_cost_basis += position_cost_basis

            logger.debug(
                f"{ticker} ({isin}): qty={quantity}, "
                f"price={historical_price}, value={position_value}, "
                f"cost={position_cost_basis}"
            )

        # Create snapshot
        snapshot = PortfolioSnapshot(
            snapshot_date=target_date,
            total_value=total_value,
            total_cost_basis=total_cost_basis,
            currency="EUR"
        )

        db.add(snapshot)
        db.commit()

        # Calculate return
        if total_cost_basis > 0:
            portfolio_return = (float(total_value) / float(total_cost_basis)) - 1
        else:
            portfolio_return = 0

        summary = {
            "status": "success",
            "snapshot_date": str(target_date),
            "total_value": float(total_value),
            "total_cost_basis": float(total_cost_basis),
            "unrealized_pnl": float(total_value - total_cost_basis),
            "portfolio_return": portfolio_return,
            "num_positions": len(historical_positions)
        }

        if missing_prices:
            summary["missing_prices"] = missing_prices
            summary["warning"] = f"Missing prices for {len(missing_prices)} positions"

        logger.info(
            f"Snapshot created for {target_date}: "
            f"value={total_value:.2f}, cost={total_cost_basis:.2f}, "
            f"return={portfolio_return:.2%}"
        )

        return summary

    except IntegrityError as e:
        # Race condition: another process already created this snapshot
        db.rollback()
        logger.debug(f"Snapshot already exists for {target_date} (race condition)")

        # Fetch existing snapshot
        existing = db.execute(
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.snapshot_date == target_date)
        ).scalar_one_or_none()

        return {
            "status": "skipped",
            "snapshot_date": str(target_date),
            "reason": "Snapshot already exists (race condition)",
            "total_value": float(existing.total_value) if existing else 0,
            "total_cost_basis": float(existing.total_cost_basis) if existing else 0
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating snapshot: {str(e)}")
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
def backfill_snapshots(self, start_date: str, end_date: str = None):
    """
    Backfill historical snapshots for a date range.

    This is a utility task for creating historical snapshots.
    Useful for populating historical data after setting up the system.

    Args:
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD). If None, uses today.

    Returns:
        dict: Backfill summary
    """
    logger.info(f"Starting snapshot backfill from {start_date} to {end_date or 'today'}")

    from datetime import timedelta

    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date) if end_date else date.today()

    if start > end:
        raise ValueError("start_date must be before end_date")

    created = 0
    skipped = 0
    failed = 0
    current_date = start

    while current_date <= end:
        try:
            result = create_daily_snapshot(snapshot_date=str(current_date))

            if result["status"] == "success":
                created += 1
            elif result["status"] == "skipped":
                skipped += 1

            logger.info(f"Processed snapshot for {current_date}: {result['status']}")

        except Exception as e:
            logger.error(f"Failed to create snapshot for {current_date}: {str(e)}")
            failed += 1

        current_date += timedelta(days=1)

    summary = {
        "status": "completed",
        "start_date": str(start),
        "end_date": str(end),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "total_days": (end - start).days + 1
    }

    logger.info(
        f"Backfill complete: {created} created, {skipped} skipped, "
        f"{failed} failed over {summary['total_days']} days"
    )

    return summary
