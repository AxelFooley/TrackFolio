"""
Metric calculation tasks.

Calculates and caches IRR, TWR, and other portfolio metrics.
"""
from celery import shared_task
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
import logging

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import Position, Transaction, PriceHistory, CachedMetrics, TransactionType
from app.services.calculations import FinancialCalculations
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
def calculate_all_metrics(self):
    """
    Calculate and cache IRR and other metrics for all active positions.

    This task is idempotent - it will update existing metrics or create new ones.
    Scheduled to run daily at 23:15 CET (after price updates).

    Returns:
        dict: Summary of metrics calculated
    """
    logger.info("Starting metric calculation task")

    db = SyncSessionLocal()

    try:
        # Get all active positions (quantity > 0)
        result = db.execute(
            select(Position)
            .where(Position.quantity > 0)
            .order_by(Position.current_ticker)
        )
        active_positions = result.scalars().all()

        if not active_positions:
            logger.info("No active positions found. Skipping metric calculation.")
            return {
                "status": "success",
                "calculated": 0,
                "failed": 0,
                "message": "No active positions"
            }

        logger.info(f"Calculating metrics for {len(active_positions)} positions")

        # Track results
        calculated = 0
        failed = 0
        failed_tickers = []

        # Calculate expiry (24 hours from now)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        for position in active_positions:
            ticker = position.current_ticker  # Use current_ticker

            try:
                # Calculate position metrics
                metrics = await_calculate_position_metrics(db, ticker)

                if not metrics:
                    logger.warning(f"Could not calculate metrics for {ticker}")
                    failed += 1
                    failed_tickers.append(ticker)
                    continue

                # Upsert cached metrics
                # First try to update existing record
                stmt = (
                    update(CachedMetrics)
                    .where(
                        CachedMetrics.metric_type == "position_metrics",
                        CachedMetrics.metric_key == ticker
                    )
                    .values(
                        metric_value=metrics,
                        calculated_at=datetime.utcnow(),
                        expires_at=expires_at
                    )
                )

                result = db.execute(stmt)
                db.commit()

                if result.rowcount == 0:
                    # No existing record, insert new one
                    cached_metric = CachedMetrics(
                        metric_type="position_metrics",
                        metric_key=ticker,
                        metric_value=metrics,
                        calculated_at=datetime.utcnow(),
                        expires_at=expires_at
                    )
                    db.add(cached_metric)
                    db.commit()

                logger.info(f"Calculated metrics for {ticker}: IRR={metrics.get('irr')}")
                calculated += 1

            except Exception as e:
                db.rollback()
                logger.error(f"Error calculating metrics for {ticker}: {str(e)}")
                failed += 1
                failed_tickers.append(ticker)

        # Calculate portfolio-level metrics
        try:
            portfolio_metrics = await_calculate_portfolio_metrics(db)

            if portfolio_metrics:
                # Upsert portfolio metrics
                stmt = (
                    update(CachedMetrics)
                    .where(
                        CachedMetrics.metric_type == "portfolio_metrics",
                        CachedMetrics.metric_key == "global"
                    )
                    .values(
                        metric_value=portfolio_metrics,
                        calculated_at=datetime.utcnow(),
                        expires_at=expires_at
                    )
                )

                result = db.execute(stmt)
                db.commit()

                if result.rowcount == 0:
                    cached_metric = CachedMetrics(
                        metric_type="portfolio_metrics",
                        metric_key="global",
                        metric_value=portfolio_metrics,
                        calculated_at=datetime.utcnow(),
                        expires_at=expires_at
                    )
                    db.add(cached_metric)
                    db.commit()

                logger.info(f"Calculated portfolio metrics: {portfolio_metrics}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error calculating portfolio metrics: {str(e)}")

        # Clean up expired metrics
        try:
            stmt = delete(CachedMetrics).where(
                CachedMetrics.expires_at < datetime.utcnow()
            )
            result = db.execute(stmt)
            db.commit()

            if result.rowcount > 0:
                logger.info(f"Cleaned up {result.rowcount} expired metrics")

        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up expired metrics: {str(e)}")

        # Summary
        summary = {
            "status": "success",
            "calculated": calculated,
            "failed": failed,
            "total_positions": len(active_positions)
        }

        if failed_tickers:
            summary["failed_tickers"] = failed_tickers

        logger.info(
            f"Metric calculation complete: {calculated} calculated, {failed} failed "
            f"out of {len(active_positions)} positions"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in metric calculation task: {str(e)}")
        raise

    finally:
        db.close()


def await_calculate_position_metrics(db, ticker: str) -> dict:
    """
    Calculate all metrics for a single position.

    Args:
        db: Database session
        ticker: Ticker symbol (current_ticker)

    Returns:
        dict: Metrics including IRR, TWR, total_invested, current_value, etc.
    """
    # Get position by current_ticker
    position = db.execute(
        select(Position).where(Position.current_ticker == ticker)
    ).scalar_one_or_none()

    if not position or position.quantity <= 0:
        return None

    # Get all transactions for this ISIN (not ticker!)
    transactions = db.execute(
        select(Transaction)
        .where(Transaction.isin == position.isin)
        .order_by(Transaction.operation_date)
    ).scalars().all()

    if not transactions:
        return None

    # Get latest price
    latest_price_record = db.execute(
        select(PriceHistory)
        .where(PriceHistory.ticker == ticker)
        .order_by(PriceHistory.date.desc())
        .limit(1)
    ).scalar_one_or_none()

    if not latest_price_record:
        # Try fetching from API
        price_fetcher = PriceFetcher()
        price_data = price_fetcher.fetch_latest_price(ticker, position.isin)

        if price_data and price_data.get("close"):
            current_price = Decimal(str(price_data["close"]))
        else:
            logger.warning(f"No price available for {ticker}")
            return None
    else:
        current_price = latest_price_record.close

    # Calculate current value
    current_value = position.quantity * current_price

    # Build cash flows for IRR calculation
    cash_flows = []
    total_invested = Decimal("0")

    for txn in transactions:
        if txn.transaction_type == TransactionType.BUY:
            # Outflow (negative)
            cash_flow = -(txn.amount_eur + txn.fees)
            total_invested += abs(cash_flow)
        elif txn.transaction_type == TransactionType.SELL:
            # Inflow (positive)
            cash_flow = txn.amount_eur - txn.fees
        else:
            # DIVIDEND - skip for IRR cash flow calculation
            continue

        # Append as tuple (date, amount) as expected by calculate_irr
        cash_flows.append((txn.operation_date, cash_flow))

    if not cash_flows:
        return None

    # Calculate IRR
    try:
        irr = FinancialCalculations.calculate_irr(
            cash_flows=cash_flows,
            current_value=current_value,
            current_date=date.today()
        )
    except Exception as e:
        logger.warning(f"Could not calculate IRR for {ticker}: {str(e)}")
        irr = None

    # Calculate TWR (simplified - using first and last values)
    first_date = transactions[0].operation_date
    days_held = (date.today() - first_date).days

    if days_held > 0 and total_invested > 0:
        try:
            twr = FinancialCalculations.calculate_twr(
                beginning_value=total_invested,
                ending_value=current_value,
                days=days_held
            )
        except Exception as e:
            logger.warning(f"Could not calculate TWR for {ticker}: {str(e)}")
            twr = None
    else:
        twr = None

    # Calculate simple return
    if total_invested > 0:
        simple_return = (float(current_value) / float(total_invested)) - 1
    else:
        simple_return = 0

    # Build metrics dictionary
    metrics = {
        "ticker": ticker,
        "quantity": float(position.quantity),
        "average_cost": float(position.average_cost),
        "current_price": float(current_price),
        "current_value": float(current_value),
        "total_invested": float(total_invested),
        "unrealized_pnl": float(current_value - total_invested),
        "simple_return": simple_return,
        "irr": irr,
        "twr": twr,
        "first_purchase_date": str(first_date),
        "days_held": days_held,
        "calculated_at": datetime.utcnow().isoformat()
    }

    return metrics


def await_calculate_portfolio_metrics(db) -> dict:
    """
    Calculate portfolio-level metrics.

    Args:
        db: Database session

    Returns:
        dict: Portfolio metrics
    """
    # Get all active positions
    positions = db.execute(
        select(Position).where(Position.quantity > 0)
    ).scalars().all()

    if not positions:
        return None

    total_value = Decimal("0")
    total_cost = Decimal("0")

    # Calculate totals
    for position in positions:
        # Get latest price (use current_ticker)
        latest_price_record = db.execute(
            select(PriceHistory)
            .where(PriceHistory.ticker == position.current_ticker)
            .order_by(PriceHistory.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if latest_price_record:
            current_price = latest_price_record.close
            current_value = position.quantity * current_price
            total_value += current_value
            total_cost += position.quantity * position.average_cost

    # Calculate portfolio return
    if total_cost > 0:
        portfolio_return = (float(total_value) / float(total_cost)) - 1
    else:
        portfolio_return = 0

    metrics = {
        "total_value": float(total_value),
        "total_cost": float(total_cost),
        "unrealized_pnl": float(total_value - total_cost),
        "portfolio_return": portfolio_return,
        "num_positions": len(positions),
        "calculated_at": datetime.utcnow().isoformat()
    }

    return metrics
