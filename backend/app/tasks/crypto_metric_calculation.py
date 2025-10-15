"""
Crypto metric calculation tasks.

Calculates and caches IRR, TWR, and other crypto portfolio metrics.
"""
from celery import shared_task
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
import logging

from app.celery_app import celery_app
from app.database import SyncSessionLocal
from app.models import CachedMetrics
from app.models.crypto import CryptoPortfolio, CryptoTransaction, CryptoTransactionType
from app.services.price_fetcher import PriceFetcher
from sqlalchemy.dialects.postgresql import insert

logger = logging.getLogger(__name__)

# Fallback EURUSD rate when real-time data is unavailable (USD per EUR)
DEFAULT_EURUSD_FALLBACK_RATE = Decimal("0.92")


def _calculate_holdings_from_transactions(transactions):
    """
    Calculate current holdings from transaction history.

    Args:
        transactions: List of CryptoTransaction objects

    Returns:
        dict: Holdings keyed by symbol with quantity and total_cost
    """
    holdings = {}

    for txn in transactions:
        symbol = txn.symbol
        if symbol not in holdings:
            holdings[symbol] = {
                "quantity": Decimal("0"),
                "total_cost": Decimal("0"),
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

    return holdings


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
    Calculate and cache per-portfolio and aggregated crypto metrics for all active crypto portfolios.
    
    Performs portfolio-level metric computation, upserts each portfolio's metrics into CachedMetrics with a 24-hour expiry, computes and upserts global metrics, cleans up expired cached entries, and aggregates success/failure counts.
    
    Returns:
        dict: Summary with keys "status", "calculated" (number cached), "failed" (number failed), "total_portfolios", and optionally "failed_portfolios" (list of failed portfolio names).
    """
    logger.info("Starting crypto metric calculation task")

    db = SyncSessionLocal()

    try:
        # Get all active crypto portfolios
        result = db.execute(
            select(CryptoPortfolio)
            .where(CryptoPortfolio.is_active)
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
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)

        for portfolio in active_portfolios:
            try:
                # Calculate portfolio metrics
                metrics = calculate_crypto_portfolio_metrics(db, portfolio.id)

                if not metrics:
                    logger.warning(f"Could not calculate metrics for crypto portfolio {portfolio.name}")
                    failed += 1
                    failed_portfolios.append(portfolio.name)
                    continue

                # Atomic upsert (PostgreSQL)
                stmt = insert(CachedMetrics).values(
                    metric_type="crypto_portfolio_metrics",
                    metric_key=str(portfolio.id),
                    metric_value=metrics,
                    calculated_at=datetime.now(timezone.utc),
                    expires_at=expires_at
                ).on_conflict_do_update(
                    index_elements=["metric_type", "metric_key"],
                    set_={
                        "metric_value": metrics,
                        "calculated_at": datetime.now(timezone.utc),
                        "expires_at": expires_at,
                    }
                )
                db.execute(stmt)
                db.commit()

                calculated += 1
                logger.info(f"Cached metrics for crypto portfolio {portfolio.name}")

            except Exception:
                db.rollback()
                logger.exception(f"Error calculating crypto metrics for portfolio {portfolio.name}")
                failed += 1
                failed_portfolios.append(portfolio.name)

        # Calculate global crypto metrics (across all portfolios)
        try:
            global_metrics = calculate_global_crypto_metrics(db)

            if global_metrics:
                # Atomic upsert (PostgreSQL)
                stmt = insert(CachedMetrics).values(
                    metric_type="crypto_global_metrics",
                    metric_key="global",
                    metric_value=global_metrics,
                    calculated_at=datetime.now(timezone.utc),
                    expires_at=expires_at
                ).on_conflict_do_update(
                    index_elements=["metric_type", "metric_key"],
                    set_={
                        "metric_value": global_metrics,
                        "calculated_at": datetime.now(timezone.utc),
                        "expires_at": expires_at,
                    }
                )
                db.execute(stmt)
                db.commit()

                logger.info(f"Calculated global crypto metrics: Total value = {global_metrics.get('total_value_eur')}")

        except Exception:
            db.rollback()
            logger.exception("Error calculating global crypto metrics")

        # Clean up expired metrics
        try:
            stmt = delete(CachedMetrics).where(
                CachedMetrics.expires_at < datetime.now(timezone.utc)
            )
            result = db.execute(stmt)
            db.commit()

            if result.rowcount > 0:
                logger.info(f"Cleaned up {result.rowcount} expired crypto metrics")

        except Exception:
            db.rollback()
            logger.exception("Error cleaning up expired crypto metrics")

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

    except Exception:
        logger.exception("Fatal error in crypto metric calculation task")
        raise

    finally:
        db.close()


def calculate_crypto_portfolio_metrics(db, portfolio_id: int) -> dict:
    """
    Compute portfolio-level crypto metrics for the specified portfolio.
    
    Calculates current value, cost basis, unrealized P&L, simple total return, per-symbol holdings and asset allocation using transaction history and realtime prices. Returns None if the portfolio does not exist or is not active.
    
    Parameters:
        portfolio_id (int): ID of the crypto portfolio to compute metrics for.
    
    Returns:
        dict or None: Metrics dictionary when the portfolio is found and active, otherwise `None`.
        The metrics dictionary includes at least the following keys:
            - portfolio_id: portfolio identifier
            - portfolio_name: portfolio name
            - total_value_eur: total market value in EUR
            - total_value_usd: total market value in USD
            - total_cost_basis: aggregated cost basis
            - unrealized_pnl_eur: unrealized profit/loss in EUR
            - unrealized_pnl_pct: unrealized profit/loss as a percentage
            - total_return_pct: simple total return percentage
            - asset_allocation: mapping of symbol -> {percentage, value_eur, value_usd}
            - holdings: mapping of symbol -> per-symbol metrics (quantity, average_cost, current_price_eur/usd, value_eur/usd, cost_basis, unrealized_pnl_eur, unrealized_pnl_pct)
            - num_positions: number of active positions
            - base_currency: portfolio base currency code
            - calculated_at: ISO8601 UTC timestamp of calculation
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
            "calculated_at": datetime.now(timezone.utc).isoformat()
        }

    # Get current holdings using helper function
    holdings = _calculate_holdings_from_transactions(transactions)

    # Recalculate total cost basis from holdings
    total_cost_basis = sum(holding["total_cost"] for holding in holdings.values())

    # Get current prices and calculate values
    total_value_eur = Decimal("0")
    total_value_usd = Decimal("0")
    asset_allocation = {}
    current_holdings = {}

    # Reuse one fetcher per portfolio
    price_fetcher = PriceFetcher()

    # Fetch EURUSD once (USD per EUR). Convert USD->EUR by dividing.
    eurusd = price_fetcher.fetch_realtime_price("EURUSD=X")
    eurusd_rate = None
    if eurusd and eurusd.get("current_price"):
        try:
            eurusd_rate = Decimal(str(eurusd["current_price"]))
        except Exception:
            eurusd_rate = None

    for symbol, holding in holdings.items():
        if holding["quantity"] <= 0:
            continue

        # Get current price from Yahoo Finance
        yahoo_symbol = f"{symbol}-USD"
        price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

        if price_data and price_data.get("current_price"):
            price_usd = price_data["current_price"]
            price_eur = (price_usd / eurusd_rate) if eurusd_rate and eurusd_rate != 0 else (price_usd * DEFAULT_EURUSD_FALLBACK_RATE)

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
    # Note: unrealized_pnl_pct and total_return_pct are intentionally the same for crypto portfolios.
    # Both represent the simple return calculation. This differs from traditional portfolios where
    # IRR and TWR might be different. For crypto, we use the same calculation to maintain consistency
    # with the frontend expectations.
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


def calculate_crypto_position_metrics(db, portfolio_id: int) -> dict:
    """
    Calculate per-symbol position metrics for a crypto portfolio.
    
    Parameters:
        portfolio_id (int): ID of the crypto portfolio to analyze.
    
    Returns:
        dict: Mapping from symbol (str) to a metrics dictionary containing:
            - symbol (str)
            - quantity (float)
            - average_cost (float)
            - current_price_eur (float)
            - current_value_eur (float)
            - cost_basis (float)
            - unrealized_pnl_eur (float)
            - unrealized_pnl_pct (float)
            - irr (float)
            - calculated_at (str, UTC ISO timestamp)
    
        Returns an empty dict if the portfolio has no transactions or no positive-quantity positions.
    """
    # Get portfolio transactions
    transactions = db.execute(
        select(CryptoTransaction)
        .where(CryptoTransaction.portfolio_id == portfolio_id)
        .order_by(CryptoTransaction.timestamp)
    ).scalars().all()

    if not transactions:
        return {}

    # Calculate holdings using helper function
    holdings = _calculate_holdings_from_transactions(transactions)

    # Calculate metrics for each symbol
    metrics = {}

    # Reuse one fetcher
    price_fetcher = PriceFetcher()

    # Fetch EURUSD rate
    eurusd = price_fetcher.fetch_realtime_price("EURUSD=X")
    eurusd_rate = None
    if eurusd and eurusd.get("current_price"):
        try:
            eurusd_rate = Decimal(str(eurusd["current_price"]))
        except Exception:
            eurusd_rate = None

    for symbol, holding in holdings.items():
        if holding["quantity"] <= 0:
            continue

        # Get current price from Yahoo Finance
        yahoo_symbol = f"{symbol}-USD"
        price_data = price_fetcher.fetch_realtime_price(yahoo_symbol)

        if price_data and price_data.get("current_price"):
            price_usd = price_data["current_price"]
            price_eur = (price_usd / eurusd_rate) if eurusd_rate and eurusd_rate != 0 else (price_usd * DEFAULT_EURUSD_FALLBACK_RATE)
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
                "calculated_at": datetime.now(timezone.utc).isoformat()
            }

    return metrics


def calculate_global_crypto_metrics(db) -> dict:
    """
    Compute aggregated crypto metrics across all active portfolios.
    
    If there are active portfolios, returns a dictionary containing aggregated totals, returns, asset allocation, counts, and a UTC ISO timestamp; returns `None` if no active portfolios are found.
    
    Returns:
        dict or None: Aggregated metrics with keys:
            - total_value_eur (float): Sum market value in EUR across portfolios.
            - total_value_usd (float): Sum market value in USD across portfolios.
            - total_cost_basis (float): Sum of cost basis across portfolios.
            - unrealized_pnl_eur (float): total_value_eur minus total_cost_basis.
            - unrealized_pnl_pct (float): percent unrealized profit/loss based on EUR totals.
            - total_return_pct (float): same as unrealized_pnl_pct (simple aggregate return).
            - asset_allocation (dict): mapping symbol -> {percentage (float), value_eur (float), value_usd (float)}.
            - num_portfolios (int): number of active portfolios included.
            - num_positions (int): number of distinct symbols held across all portfolios.
            - calculated_at (str): UTC ISO timestamp when metrics were calculated.
    """
    # Get all active crypto portfolios
    portfolios = db.execute(
        select(CryptoPortfolio).where(CryptoPortfolio.is_active)
    ).scalars().all()

    if not portfolios:
        return None

    total_value_eur = Decimal("0")
    total_value_usd = Decimal("0")
    total_cost_basis = Decimal("0")
    all_holdings = {}

    # Aggregate across all portfolios
    for portfolio in portfolios:
        portfolio_metrics = calculate_crypto_portfolio_metrics(db, portfolio.id)
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