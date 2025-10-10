"""
Crypto portfolio snapshot tasks.

Creates daily snapshots of crypto portfolio values for historical performance tracking.
"""
from celery import shared_task
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
import logging
import json

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import CachedMetrics
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType
from app.models.crypto_portfolio_snapshot import CryptoPortfolioSnapshot
from app.models.price_history import PriceHistory
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
def create_daily_crypto_snapshots(self):
    """
    Create daily snapshots for all active crypto portfolios.

    This task is idempotent - it will update existing snapshots or create new ones.
    Scheduled to run daily at 23:30 CET (after crypto metrics calculation).

    Returns:
        dict: Summary of snapshots created/updated
    """
    logger.info("Starting daily crypto portfolio snapshot task")

    db = SyncSessionLocal()

    try:
        # Get all active crypto portfolios
        result = db.execute(
            select(CryptoPortfolio)
            .where(CryptoPortfolio.is_active == True)
            .order_by(CryptoPortfolio.name)
        )
        active_portfolios = result.scalars().all()

        if not active_portfolios:
            logger.info("No active crypto portfolios found. Skipping crypto snapshot creation.")
            return {
                "status": "success",
                "created": 0,
                "updated": 0,
                "failed": 0,
                "message": "No active crypto portfolios"
            }

        logger.info(f"Creating snapshots for {len(active_portfolios)} crypto portfolios")

        # Get today's date
        snapshot_date = date.today()

        # Track results
        created = 0
        updated = 0
        failed = 0
        failed_portfolios = []

        for portfolio in active_portfolios:
            try:
                # Calculate portfolio metrics for the snapshot
                snapshot_data = await_calculate_crypto_snapshot_data(db, portfolio.id, snapshot_date)

                if not snapshot_data:
                    logger.warning(f"Could not calculate snapshot data for crypto portfolio {portfolio.name}")
                    failed += 1
                    failed_portfolios.append(portfolio.name)
                    continue

                # Check if snapshot already exists for this date
                existing = db.execute(
                    select(CryptoPortfolioSnapshot)
                    .where(
                        CryptoPortfolioSnapshot.portfolio_id == portfolio.id,
                        CryptoPortfolioSnapshot.snapshot_date == snapshot_date
                    )
                ).scalar_one_or_none()

                if existing:
                    # Update existing snapshot
                    existing.total_value_eur = snapshot_data["total_value_eur"]
                    existing.total_value_usd = snapshot_data["total_value_usd"]
                    existing.total_cost_basis = snapshot_data["total_cost_basis"]
                    existing.base_currency = snapshot_data["base_currency"]
                    existing.holdings_breakdown = snapshot_data["holdings_breakdown"]
                    existing.total_return_pct = snapshot_data["total_return_pct"]
                    existing.created_at = datetime.utcnow()

                    db.commit()
                    logger.info(f"Updated crypto snapshot for portfolio {portfolio.name} on {snapshot_date}")
                    updated += 1
                else:
                    # Create new snapshot
                    snapshot = CryptoPortfolioSnapshot(
                        portfolio_id=portfolio.id,
                        snapshot_date=snapshot_date,
                        total_value_eur=snapshot_data["total_value_eur"],
                        total_value_usd=snapshot_data["total_value_usd"],
                        total_cost_basis=snapshot_data["total_cost_basis"],
                        base_currency=snapshot_data["base_currency"],
                        holdings_breakdown=snapshot_data["holdings_breakdown"],
                        total_return_pct=snapshot_data["total_return_pct"]
                    )

                    db.add(snapshot)
                    db.commit()
                    logger.info(f"Created crypto snapshot for portfolio {portfolio.name} on {snapshot_date}")
                    created += 1

            except IntegrityError as e:
                # Race condition: another process already created this snapshot
                db.rollback()
                logger.debug(f"Snapshot already exists for portfolio {portfolio.name} on {snapshot_date} (race condition)")
                created += 1  # Count as success since the snapshot exists

            except Exception as e:
                db.rollback()
                logger.error(f"Error creating crypto snapshot for portfolio {portfolio.name}: {str(e)}")
                failed += 1
                failed_portfolios.append(portfolio.name)

        # Clean up old snapshots (keep last 2 years)
        try:
            # Subtract ~2 years safely to avoid Feb 29 invalid dates
            cleanup_date = snapshot_date - timedelta(days=730)
            stmt = select(CryptoPortfolioSnapshot).where(
                CryptoPortfolioSnapshot.snapshot_date < cleanup_date
            )
            old_snapshots = db.execute(stmt).scalars().all()

            if old_snapshots:
                # Delete old snapshots
                delete_stmt = delete(CryptoPortfolioSnapshot).where(
                    CryptoPortfolioSnapshot.snapshot_date < cleanup_date
                )
                result = db.execute(delete_stmt)
                db.commit()
                logger.info(f"Cleaned up {result.rowcount} old crypto snapshots (older than {cleanup_date})")

        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up old crypto snapshots: {str(e)}")

        # Summary
        summary = {
            "status": "success",
            "created": created,
            "updated": updated,
            "failed": failed,
            "total_portfolios": len(active_portfolios),
            "snapshot_date": str(snapshot_date)
        }

        if failed_portfolios:
            summary["failed_portfolios"] = failed_portfolios

        logger.info(
            f"Crypto snapshot creation complete: {created} created, {updated} updated, "
            f"{failed} failed out of {len(active_portfolios)} portfolios"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in crypto snapshot task: {str(e)}")
        raise

    finally:
        db.close()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3, 'countdown': 5}
)
def create_crypto_snapshot_for_portfolio(self, portfolio_id: int, snapshot_date: str = None):
    """
    Create a snapshot for a specific crypto portfolio.

    This is a utility task that can be called manually or from API endpoints.

    Args:
        portfolio_id: Crypto portfolio ID
        snapshot_date: Date string (YYYY-MM-DD). If None, uses today's date.

    Returns:
        dict: Snapshot creation result
    """
    logger.info(f"Creating crypto snapshot for portfolio {portfolio_id}")

    db = SyncSessionLocal()

    try:
        # Parse date
        if snapshot_date:
            target_date = date.fromisoformat(snapshot_date)
        else:
            target_date = date.today()

        # Get portfolio
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            logger.warning(f"Crypto portfolio {portfolio_id} not found")
            return {
                "status": "failed",
                "portfolio_id": portfolio_id,
                "snapshot_date": str(target_date),
                "reason": "Portfolio not found"
            }

        # Calculate snapshot data
        snapshot_data = await_calculate_crypto_snapshot_data(db, portfolio_id, target_date)

        if not snapshot_data:
            logger.warning(f"Could not calculate snapshot data for crypto portfolio {portfolio_id}")
            return {
                "status": "failed",
                "portfolio_id": portfolio_id,
                "snapshot_date": str(target_date),
                "reason": "Could not calculate snapshot data"
            }

        # Check if snapshot already exists
        existing = db.execute(
            select(CryptoPortfolioSnapshot)
            .where(
                CryptoPortfolioSnapshot.portfolio_id == portfolio_id,
                CryptoPortfolioSnapshot.snapshot_date == target_date
            )
        ).scalar_one_or_none()

        if existing:
            logger.info(f"Snapshot already exists for portfolio {portfolio_id} on {target_date}")
            return {
                "status": "skipped",
                "portfolio_id": portfolio_id,
                "portfolio_name": portfolio.name,
                "snapshot_date": str(target_date),
                "reason": "Snapshot already exists"
            }

        # Create new snapshot
        snapshot = CryptoPortfolioSnapshot(
            portfolio_id=portfolio_id,
            snapshot_date=target_date,
            total_value_eur=snapshot_data["total_value_eur"],
            total_value_usd=snapshot_data["total_value_usd"],
            total_cost_basis=snapshot_data["total_cost_basis"],
            base_currency=snapshot_data["base_currency"],
            holdings_breakdown=snapshot_data["holdings_breakdown"],
            total_return_pct=snapshot_data["total_return_pct"]
        )

        db.add(snapshot)
        db.commit()

        logger.info(f"Created crypto snapshot for portfolio {portfolio.name} on {target_date}")

        return {
            "status": "success",
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "snapshot_date": str(target_date),
            "total_value_eur": float(snapshot_data["total_value_eur"]),
            "total_value_usd": float(snapshot_data["total_value_usd"]),
            "total_return_pct": float(snapshot_data["total_return_pct"])
        }

    except IntegrityError:
        db.rollback()
        logger.debug(f"Snapshot already exists for portfolio {portfolio_id} (race condition)")
        return {
            "status": "skipped",
            "portfolio_id": portfolio_id,
            "snapshot_date": str(target_date),
            "reason": "Snapshot already exists"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating crypto snapshot for portfolio {portfolio_id}: {str(e)}")
        raise

    finally:
        db.close()


def await_calculate_crypto_snapshot_data(db, portfolio_id: int, snapshot_date: date) -> dict:
    """
    Calculate snapshot data for a crypto portfolio.

    Args:
        db: Database session
        portfolio_id: Crypto portfolio ID
        snapshot_date: Date of the snapshot

    Returns:
        dict: Snapshot data
    """
    # Get portfolio
    portfolio = db.execute(
        select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
    ).scalar_one_or_none()

    if not portfolio:
        return None

    # Get all transactions for this portfolio
    transactions = db.execute(
        select(CryptoTransaction)
        .where(
            CryptoTransaction.portfolio_id == portfolio_id,
            CryptoTransaction.timestamp <= datetime.combine(snapshot_date, datetime.max.time())
        )
        .order_by(CryptoTransaction.timestamp)
    ).scalars().all()

    if not transactions:
        return {
            "total_value_eur": Decimal("0"),
            "total_value_usd": Decimal("0"),
            "total_cost_basis": Decimal("0"),
            "base_currency": portfolio.base_currency.value,
            "holdings_breakdown": json.dumps({}),
            "total_return_pct": Decimal("0")
        }

    # Calculate current holdings
    holdings = {}

    for txn in transactions:
        symbol = txn.symbol
        if symbol not in holdings:
            holdings[symbol] = {
                "quantity": Decimal("0"),
                "total_cost": Decimal("0")
            }

        if txn.transaction_type == CryptoTransactionType.BUY or txn.transaction_type == CryptoTransactionType.TRANSFER_IN:
            # Add to position
            holdings[symbol]["quantity"] += txn.quantity
            holdings[symbol]["total_cost"] += txn.total_amount
        elif txn.transaction_type == CryptoTransactionType.SELL or txn.transaction_type == CryptoTransactionType.TRANSFER_OUT:
            # Calculate average cost per unit before reducing position
            if holdings[symbol]["quantity"] > 0:
                average_cost_per_unit = holdings[symbol]["total_cost"] / holdings[symbol]["quantity"]
            else:
                average_cost_per_unit = Decimal("0")

            # Reduce quantity
            sold_quantity = min(txn.quantity, holdings[symbol]["quantity"])  # Prevent negative
            holdings[symbol]["quantity"] -= sold_quantity

            # Reduce cost basis by the cost of units sold (not by proceeds)
            cost_removed = average_cost_per_unit * sold_quantity
            holdings[symbol]["total_cost"] -= cost_removed

            # Ensure no negative values
            if holdings[symbol]["quantity"] < 0:
                holdings[symbol]["quantity"] = Decimal("0")
            if holdings[symbol]["total_cost"] < 0:
                holdings[symbol]["total_cost"] = Decimal("0")

    # Recalculate total cost basis from holdings
    total_cost_basis = sum(holding["total_cost"] for holding in holdings.values())

    # Get current prices for non-zero holdings
    total_value_eur = Decimal("0")
    total_value_usd = Decimal("0")
    holdings_breakdown = {}

    for symbol, holding in holdings.items():
        if holding["quantity"] <= 0:
            continue

        # Get current price (for snapshot, we want the price as of snapshot_date)
        # Try to get the most recent price from price_history table first
        price_record = db.execute(
            select(PriceHistory)
            .where(
                PriceHistory.ticker == symbol,
                PriceHistory.date <= snapshot_date
            )
            .order_by(PriceHistory.date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if price_record:
            price_eur = Decimal(str(price_record.close))
            # Derive USD via dynamic FX if available
            try:
                fx = PriceFetcher()
                import asyncio
                eur_usd = asyncio.run(fx.fetch_fx_rate("EUR", "USD"))  # EURUSD=X
                if eur_usd and eur_usd > 0:
                    price_usd = price_eur * eur_usd
                else:
                    logger.warning("EUR/USD FX unavailable; skipping USD conversion")
                    price_usd = None
            except Exception:
                logger.exception("FX conversion failed; skipping USD conversion")
                price_usd = None
        else:
            # Try to get current price from Yahoo Finance
            price_fetcher = PriceFetcher()
            yahoo_symbol = f"{symbol}-USD"
            price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)
            if price_data and price_data.get("current_price"):
                price_usd = price_data["current_price"]
                # Convert with dynamic FX
                try:
                    import asyncio
                    usd_eur = asyncio.run(price_fetcher.fetch_fx_rate("USD", "EUR"))  # USDEUR=X
                    if usd_eur and usd_eur > 0:
                        price_eur = price_usd * usd_eur
                    else:
                        logger.warning("USD/EUR FX unavailable; skipping holding")
                        continue
                except Exception:
                    logger.exception("FX conversion failed; skipping holding")
                    continue
            else:
                # No fallback - skip this holding if no price data available
                logger.warning(f"Could not get price for {symbol} on {snapshot_date}. Skipping holding from snapshot.")
                continue

        value_eur = holding["quantity"] * price_eur
        value_usd = holding["quantity"] * price_usd

        total_value_eur += value_eur
        total_value_usd += value_usd

        holdings_breakdown[symbol] = {
            "quantity": float(holding["quantity"]),
            "value_eur": float(value_eur),
            "value_usd": float(value_usd),
            "percentage": 0  # Will be calculated below
        }

    # Calculate percentages
    if total_value_eur > 0:
        for symbol, holding in holdings_breakdown.items():
            holding["percentage"] = float((Decimal(str(holding["value_eur"])) / total_value_eur) * 100)

    # Calculate total return percentage
    total_return_pct = ((total_value_eur / total_cost_basis) - 1) * 100 if total_cost_basis > 0 else 0

    return {
        "total_value_eur": total_value_eur,
        "total_value_usd": total_value_usd,
        "total_cost_basis": total_cost_basis,
        "base_currency": portfolio.base_currency.value,
        "holdings_breakdown": json.dumps(holdings_breakdown),
        "total_return_pct": Decimal(str(total_return_pct))
    }


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 2, 'countdown': 60}
)
def backfill_crypto_snapshots(self, portfolio_id: int, start_date: str, end_date: str = None):
    """
    Backfill historical snapshots for a crypto portfolio.

    Args:
        portfolio_id: Crypto portfolio ID
        start_date: Start date string (YYYY-MM-DD)
        end_date: End date string (YYYY-MM-DD). If None, uses today's date.

    Returns:
        dict: Summary of snapshots backfilled
    """
    logger.info(f"Starting crypto snapshot backfill for portfolio {portfolio_id}")

    db = SyncSessionLocal()

    try:
        # Parse dates
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date) if end_date else date.today()

        # Get portfolio
        portfolio = db.execute(
            select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
        ).scalar_one_or_none()

        if not portfolio:
            logger.error(f"Crypto portfolio {portfolio_id} not found")
            return {"status": "failed", "reason": "Portfolio not found"}

        logger.info(f"Backfilling crypto snapshots for {portfolio.name} from {start} to {end}")

        # Create snapshots for each day
        current_date = start
        created = 0
        updated = 0
        failed = 0

        while current_date <= end:
            try:
                # Check if snapshot already exists
                existing = db.execute(
                    select(CryptoPortfolioSnapshot)
                    .where(
                        CryptoPortfolioSnapshot.portfolio_id == portfolio_id,
                        CryptoPortfolioSnapshot.snapshot_date == current_date
                    )
                ).scalar_one_or_none()

                if existing:
                    updated += 1
                else:
                    # Calculate snapshot data
                    snapshot_data = await_calculate_crypto_snapshot_data(db, portfolio_id, current_date)

                    if snapshot_data:
                        snapshot = CryptoPortfolioSnapshot(
                            portfolio_id=portfolio_id,
                            snapshot_date=current_date,
                            total_value_eur=snapshot_data["total_value_eur"],
                            total_value_usd=snapshot_data["total_value_usd"],
                            total_cost_basis=snapshot_data["total_cost_basis"],
                            base_currency=snapshot_data["base_currency"],
                            holdings_breakdown=snapshot_data["holdings_breakdown"],
                            total_return_pct=snapshot_data["total_return_pct"]
                        )

                        db.add(snapshot)
                        created += 1
                    else:
                        failed += 1

                # Commit every 10 snapshots to avoid large transactions
                if (created + updated + failed) % 10 == 0:
                    db.commit()

                current_date += timedelta(days=1)

            except Exception as e:
                db.rollback()
                logger.error(f"Error creating crypto snapshot for {current_date}: {str(e)}")
                failed += 1
                current_date += timedelta(days=1)
                continue

        # Final commit
        db.commit()

        summary = {
            "status": "success",
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "start_date": str(start),
            "end_date": str(end),
            "created": created,
            "updated": updated,
            "failed": failed,
            "total_days": (end - start).days + 1
        }

        logger.info(
            f"Crypto snapshot backfill complete for {portfolio.name}: "
            f"{created} created, {updated} updated, {failed} failed"
        )

        return summary

    except Exception as e:
        db.rollback()
        logger.error(f"Error backfilling crypto snapshots for portfolio {portfolio_id}: {str(e)}")
        raise

    finally:
        db.close()