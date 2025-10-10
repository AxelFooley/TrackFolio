"""
Crypto metric calculation tasks.

Calculates and caches IRR, TWR, and other crypto portfolio metrics.
"""
from celery import shared_task
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
import logging
import json

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import PriceHistory, CachedMetrics
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType
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
def calculate_crypto_metrics(self):
    """
    Calculate and cache IRR and other metrics for all crypto portfolios.

    This task is idempotent - it will update existing metrics or create new ones.
    Scheduled to run daily at 23:15 CET (after crypto price updates).

    Returns:
        dict: Summary of metrics calculated
    """
    logger.info("Starting crypto metric calculation task")

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
            logger.info("No active crypto portfolios found. Skipping crypto metric calculation.")
            return {
                "status": "success",
                "calculated": 0,
                "failed": 0,
                "message": "No active crypto portfolios"
            }

        logger.info(f"Calculating metrics for {len(active_portfolios)} crypto portfolios")

        # Track results
        calculated = 0
        failed = 0
        failed_portfolios = []

        # Calculate expiry (24 hours from now)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        for portfolio in active_portfolios:
            try:
                # Calculate portfolio metrics
                metrics = await_calculate_crypto_portfolio_metrics(db, portfolio.id)

                if not metrics:
                    logger.warning(f"Could not calculate metrics for crypto portfolio {portfolio.name}")
                    failed += 1
                    failed_portfolios.append(portfolio.name)
                    continue

# At the top of backend/app/tasks/crypto_metric_calculation.py
from sqlalchemy.dialects.postgresql import insert

# …later, in the metric‐calculation function…

                # Atomic upsert (PostgreSQL)
                stmt = insert(CachedMetrics).values(
                    metric_type="crypto_portfolio_metrics",
                    metric_key=str(portfolio.id),
                    metric_value=metrics,
                    calculated_at=datetime.utcnow(),
                    expires_at=expires_at
                ).on_conflict_do_update(
                    index_elements=["metric_type", "metric_key"],
                    set_={
                        "metric_value": metrics,
                        "calculated_at": datetime.utcnow(),
                        "expires_at": expires_at,
                    }
                )
                db.execute(stmt)
                db.commit()
                        metric_key = f"crypto_{portfolio.id}_{symbol}"

                        stmt = (
                            update(CachedMetrics)
                            .where(
                                CachedMetrics.metric_type == "crypto_position_metrics",
                                CachedMetrics.metric_key == metric_key
                            )
                            .values(
                                metric_value=symbol_metric,
                                calculated_at=datetime.utcnow(),
                                expires_at=expires_at
                            )
                        )

                        result = db.execute(stmt)
                        db.commit()

                        if result.rowcount == 0:
                            cached_metric = CachedMetrics(
                                metric_type="crypto_position_metrics",
                                metric_key=metric_key,
                                metric_value=symbol_metric,
                                calculated_at=datetime.utcnow(),
                                expires_at=expires_at
                            )
                            db.add(cached_metric)
                            db.commit()

            except Exception as e:
                db.rollback()
                logger.error(f"Error calculating crypto metrics for portfolio {portfolio.name}: {str(e)}")
                failed += 1
                failed_portfolios.append(portfolio.name)

        # Calculate global crypto metrics (across all portfolios)
        try:
            global_metrics = await_calculate_global_crypto_metrics(db)

            if global_metrics:
                # Upsert global metrics
                stmt = (
                    update(CachedMetrics)
                    .where(
                        CachedMetrics.metric_type == "crypto_global_metrics",
                        CachedMetrics.metric_key == "global"
                    )
                    .values(
                        metric_value=global_metrics,
                        calculated_at=datetime.utcnow(),
                        expires_at=expires_at
                    )
                )

                result = db.execute(stmt)
                db.commit()

                if result.rowcount == 0:
                    cached_metric = CachedMetrics(
                        metric_type="crypto_global_metrics",
                        metric_key="global",
                        metric_value=global_metrics,
                        calculated_at=datetime.utcnow(),
                        expires_at=expires_at
                    )
                    db.add(cached_metric)
                    db.commit()

                logger.info(f"Calculated global crypto metrics: Total value = {global_metrics.get('total_value_eur')}")

        except Exception as e:
            db.rollback()
            logger.error(f"Error calculating global crypto metrics: {str(e)}")

        # Clean up expired metrics
        try:
            stmt = delete(CachedMetrics).where(
                CachedMetrics.expires_at < datetime.utcnow()
            )
            result = db.execute(stmt)
            db.commit()

            if result.rowcount > 0:
                logger.info(f"Cleaned up {result.rowcount} expired crypto metrics")

        except Exception as e:
            db.rollback()
            logger.error(f"Error cleaning up expired crypto metrics: {str(e)}")

        # Summary
        summary = {
            "status": "success",
            "calculated": calculated,
            "failed": failed,
            "total_portfolios": len(active_portfolios)
        }

        if failed_portfolios:
            summary["failed_portfolios"] = failed_portfolios

        logger.info(
            f"Crypto metric calculation complete: {calculated} calculated, {failed} failed "
            f"out of {len(active_portfolios)} portfolios"
        )

        return summary

    except Exception as e:
        logger.error(f"Fatal error in crypto metric calculation task: {str(e)}")
        raise

    finally:
        db.close()


def await_calculate_crypto_portfolio_metrics(db, portfolio_id: int) -> dict:
    """
    Calculate all metrics for a crypto portfolio.

    Args:
        db: Database session
        portfolio_id: Crypto portfolio ID

    Returns:
        dict: Metrics including total value, IRR, asset allocation, etc.
    """
    # Get portfolio
    portfolio = db.execute(
        select(CryptoPortfolio).where(CryptoPortfolio.id == portfolio_id)
    ).scalar_one_or_none()

    if not portfolio or not portfolio.is_active:
        return None

    # Get all transactions for this portfolio
    transactions = db.execute(
        select(CryptoTransaction)
        .where(CryptoTransaction.portfolio_id == portfolio_id)
        .order_by(CryptoTransaction.timestamp)
    ).scalars().all()

    if not transactions:
        return {
            "portfolio_id": portfolio_id,
            "portfolio_name": portfolio.name,
            "total_value_eur": 0,
            "total_value_usd": 0,
            "total_cost_basis": 0,
            "unrealized_pnl_eur": 0,
            "unrealized_pnl_pct": 0,
            "total_return_pct": 0,
            "asset_allocation": {},
            "num_positions": 0,
            "base_currency": portfolio.base_currency.value,
            "calculated_at": datetime.utcnow().isoformat()
        }

    # Get current holdings
    holdings = {}

    for txn in transactions:
        symbol = txn.symbol
        if symbol not in holdings:
            holdings[symbol] = {
                "quantity": Decimal("0"),
                "total_cost": Decimal("0"),
                "transactions": []
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

    # Get current prices and calculate values
    total_value_eur = Decimal("0")
    total_value_usd = Decimal("0")
    asset_allocation = {}
    current_holdings = {}

    for symbol, holding in holdings.items():
        if holding["quantity"] <= 0:
            continue

        # Get current price from Yahoo Finance
        price_fetcher = PriceFetcher()
        yahoo_symbol = f"{symbol}-USD"
        price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

        if price_data and price_data.get("current_price"):
            price_usd = price_data["current_price"]
            price_eur = price_usd * Decimal("0.92")  # Use fallback conversion rate

            value_eur = holding["quantity"] * price_eur
            value_usd = holding["quantity"] * price_usd

            total_value_eur += value_eur
            total_value_usd += value_usd

            current_holdings[symbol] = {
                "quantity": float(holding["quantity"]),
                "average_cost": float(holding["total_cost"] / holding["quantity"]) if holding["quantity"] > 0 else 0,
                "current_price_eur": float(price_eur),
                "current_price_usd": float(price_usd),
                "value_eur": float(value_eur),
                "value_usd": float(value_usd),
                "cost_basis": float(holding["total_cost"]),
                "unrealized_pnl_eur": float(value_eur - holding["total_cost"]),
                "unrealized_pnl_pct": float((value_eur / holding["total_cost"] - 1) * 100) if holding["total_cost"] > 0 else 0,
            }
        else:
            # If no price available, use cost basis
            current_holdings[symbol] = {
                "quantity": float(holding["quantity"]),
                "average_cost": float(holding["total_cost"] / holding["quantity"]) if holding["quantity"] > 0 else 0,
                "current_price_eur": 0,
                "current_price_usd": 0,
                "value_eur": float(holding["total_cost"]),
                "value_usd": float(holding["total_cost"]),
                "cost_basis": float(holding["total_cost"]),
                "unrealized_pnl_eur": 0,
                "unrealized_pnl_pct": 0
            }
            total_value_eur += holding["total_cost"]
            total_value_usd += holding["total_cost"]

    # Calculate asset allocation percentages
    if total_value_eur > 0:
        for symbol, holding in current_holdings.items():
            asset_allocation[symbol] = {
                "percentage": float((Decimal(str(holding["value_eur"])) / total_value_eur) * 100),
                "value_eur": holding["value_eur"],
                "value_usd": holding["value_usd"]
            }

    # Calculate portfolio returns
    unrealized_pnl_eur = total_value_eur - total_cost_basis
    total_return_pct = ((total_value_eur / total_cost_basis) - 1) * 100 if total_cost_basis > 0 else 0

    # Build metrics dictionary
    metrics = {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio.name,
        "total_value_eur": float(total_value_eur),
        "total_value_usd": float(total_value_usd),
        "total_cost_basis": float(total_cost_basis),
        "unrealized_pnl_eur": float(unrealized_pnl_eur),
        "unrealized_pnl_pct": float(total_return_pct),
        "total_return_pct": float(total_return_pct),
        "asset_allocation": asset_allocation,
        "holdings": current_holdings,
        "num_positions": len(current_holdings),
        "base_currency": portfolio.base_currency.value,
        "calculated_at": datetime.utcnow().isoformat()
    }

    return metrics


def await_calculate_crypto_position_metrics(db, portfolio_id: int) -> dict:
    """
    Calculate metrics for each crypto position in a portfolio.

    Args:
        db: Database session
        portfolio_id: Crypto portfolio ID

    Returns:
        dict: Symbol-specific metrics
    """
    # Get portfolio transactions
    transactions = db.execute(
        select(CryptoTransaction)
        .where(CryptoTransaction.portfolio_id == portfolio_id)
        .order_by(CryptoTransaction.timestamp)
    ).scalars().all()

    if not transactions:
        return {}

    # Calculate holdings
    holdings = {}
    for txn in transactions:
        symbol = txn.symbol
        if symbol not in holdings:
            holdings[symbol] = {
                "quantity": Decimal("0"),
                "total_cost": Decimal("0"),
                "transactions": []
            }

        if txn.transaction_type in [CryptoTransactionType.BUY, CryptoTransactionType.TRANSFER_IN]:
            # Add to position
            holdings[symbol]["quantity"] += txn.quantity
            holdings[symbol]["total_cost"] += txn.total_amount
        elif txn.transaction_type in [CryptoTransactionType.SELL, CryptoTransactionType.TRANSFER_OUT]:
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

    # Calculate metrics for each symbol
    metrics = {}
    for symbol, holding in holdings.items():
        if holding["quantity"] <= 0:
            continue

        # Get current price from Yahoo Finance
        price_fetcher = PriceFetcher()
        yahoo_symbol = f"{symbol}-USD"
        price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

        if price_data and price_data.get("current_price"):
            price_usd = price_data["current_price"]
            price_eur = price_usd * Decimal("0.92")  # Use fallback conversion rate
            current_value = holding["quantity"] * price_eur

            # Calculate simple return as IRR substitute for now
            # Note: Full IRR calculation would require more complex cash flow analysis
            irr = float((current_value / holding["total_cost"] - 1) * 100) if holding["total_cost"] > 0 else 0

            metrics[symbol] = {
                "symbol": symbol,
                "quantity": float(holding["quantity"]),
                "average_cost": float(holding["total_cost"] / holding["quantity"]) if holding["quantity"] > 0 else 0,
                "current_price_eur": float(price_eur),
                "current_value_eur": float(current_value),
                "cost_basis": float(holding["total_cost"]),
                "unrealized_pnl_eur": float(current_value - holding["total_cost"]),
                "unrealized_pnl_pct": float((current_value / holding["total_cost"] - 1) * 100) if holding["total_cost"] > 0 else 0,
                "irr": irr,
                "calculated_at": datetime.utcnow().isoformat()
            }

    return metrics


def await_calculate_global_crypto_metrics(db) -> dict:
    """
    Calculate global metrics across all crypto portfolios.

    Args:
        db: Database session

    Returns:
        dict: Global crypto metrics
    """
    # Get all active crypto portfolios
    portfolios = db.execute(
        select(CryptoPortfolio).where(CryptoPortfolio.is_active == True)
    ).scalars().all()

    if not portfolios:
        return None

    total_value_eur = Decimal("0")
    total_value_usd = Decimal("0")
    total_cost_basis = Decimal("0")
    all_holdings = {}

    # Aggregate across all portfolios
    for portfolio in portfolios:
        portfolio_metrics = await_calculate_crypto_portfolio_metrics(db, portfolio.id)
        if portfolio_metrics:
            total_value_eur += Decimal(str(portfolio_metrics["total_value_eur"]))
            total_value_usd += Decimal(str(portfolio_metrics["total_value_usd"]))
            total_cost_basis += Decimal(str(portfolio_metrics["total_cost_basis"]))

            # Aggregate holdings by symbol
            for symbol, holding in portfolio_metrics.get("holdings", {}).items():
                if symbol not in all_holdings:
                    all_holdings[symbol] = {
                        "quantity": Decimal("0"),
                        "value_eur": Decimal("0"),
                        "value_usd": Decimal("0")
                    }

                all_holdings[symbol]["quantity"] += Decimal(str(holding["quantity"]))
                all_holdings[symbol]["value_eur"] += Decimal(str(holding["value_eur"]))
                all_holdings[symbol]["value_usd"] += Decimal(str(holding["value_usd"]))

    # Calculate global returns
    unrealized_pnl_eur = total_value_eur - total_cost_basis
    total_return_pct = ((total_value_eur / total_cost_basis) - 1) * 100 if total_cost_basis > 0 else 0

    # Calculate global asset allocation
    asset_allocation = {}
    if total_value_eur > 0:
        for symbol, holding in all_holdings.items():
            asset_allocation[symbol] = {
                "percentage": float((holding["value_eur"] / total_value_eur) * 100),
                "value_eur": float(holding["value_eur"]),
                "value_usd": float(holding["value_usd"])
            }

    metrics = {
        "total_value_eur": float(total_value_eur),
        "total_value_usd": float(total_value_usd),
        "total_cost_basis": float(total_cost_basis),
        "unrealized_pnl_eur": float(unrealized_pnl_eur),
        "unrealized_pnl_pct": float(total_return_pct),
        "total_return_pct": float(total_return_pct),
        "asset_allocation": asset_allocation,
        "num_portfolios": len(portfolios),
        "num_positions": len(all_holdings),
        "calculated_at": datetime.utcnow().isoformat()
    }

    return metrics