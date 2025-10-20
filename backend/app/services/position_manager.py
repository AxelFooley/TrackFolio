"""
Position manager service - Calculates and updates position data.

Recalculates positions based on transactions as per PRD Section 5.2.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging

from app.models import Transaction, Position, AssetType, TransactionType
from app.services.calculations import FinancialCalculations
from app.services.split_detector import SplitDetector

logger = logging.getLogger(__name__)


class PositionManager:
    """Manage position calculations and updates."""

    @staticmethod
    async def recalculate_position(db: AsyncSession, isin: str | None, ticker: str | None = None) -> Optional[Position]:
        """
        Recalculate position for a specific ISIN or ticker based on all transactions.

        Args:
            db: Database session
            isin: Asset ISIN (unique identifier) - can be None
            ticker: Asset ticker symbol - used when ISIN is None

        Returns:
            Updated Position object or None if no position exists
        """
        # Get all transactions for this ISIN/ticker
        if isin:
            # Query by ISIN if provided
            result = await db.execute(
                select(Transaction)
                .where(Transaction.isin == isin)
                .order_by(Transaction.operation_date)
            )
        elif ticker:
            # Query by ticker if ISIN is None
            result = await db.execute(
                select(Transaction)
                .where(Transaction.ticker == ticker)
                .order_by(Transaction.operation_date)
            )
        else:
            # No identifier provided
            return None

        transactions = result.scalars().all()

        if not transactions:
            # No transactions, delete position if it exists
            if isin:
                result = await db.execute(
                    select(Position).where(Position.isin == isin)
                )
            else:
                result = await db.execute(
                    select(Position).where(Position.current_ticker == ticker)
                )
            position = result.scalar_one_or_none()
            if position:
                await db.delete(position)
                await db.commit()
            return None

        # Convert to list of dicts for calculations
        txn_dicts = [
            {
                "transaction_type": t.transaction_type.value,
                "quantity": t.quantity,
                "amount_eur": t.amount_eur,
                "fees": t.fees,
                "price_per_share": t.price_per_share,
                "operation_date": t.operation_date
            }
            for t in transactions
        ]

        # Calculate position metrics
        quantity = FinancialCalculations.calculate_position_quantity(txn_dicts)

        # If quantity is zero or negative, position is closed
        if quantity <= 0:
            if isin:
                result = await db.execute(
                    select(Position).where(Position.isin == isin)
                )
            else:
                result = await db.execute(
                    select(Position).where(Position.current_ticker == ticker)
                )
            position = result.scalar_one_or_none()
            if position:
                await db.delete(position)
                await db.commit()
            return None

        average_cost = FinancialCalculations.calculate_average_cost(txn_dicts)
        cost_basis = FinancialCalculations.calculate_cost_basis(txn_dicts)

        # Get current ticker (most recent transaction's ticker)
        current_ticker = transactions[-1].ticker

        # Get or create position - try by ISIN first, then by ticker
        position = None
        if isin:
            result = await db.execute(
                select(Position).where(Position.isin == isin)
            )
            position = result.scalar_one_or_none()

        # If ISIN is None or not found, try to find by ticker
        if position is None and ticker:
            result = await db.execute(
                select(Position).where(Position.current_ticker == ticker)
            )
            position = result.scalar_one_or_none()

        # Get asset metadata from first transaction
        first_txn = transactions[0]
        asset_type = PositionManager._determine_asset_type(current_ticker)

        if position is None:
            # Create new position
            position = Position(
                isin=isin,  # ISIN can be None
                current_ticker=current_ticker,
                description=first_txn.description,
                asset_type=asset_type,
                quantity=quantity,
                average_cost=average_cost,
                cost_basis=cost_basis,
                last_calculated_at=datetime.utcnow()
            )
            db.add(position)
        else:
            # Update existing position
            position.current_ticker = current_ticker  # Update to latest ticker
            position.isin = isin  # Update ISIN if we now have one
            position.quantity = quantity
            position.average_cost = average_cost
            position.cost_basis = cost_basis
            position.last_calculated_at = datetime.utcnow()
            position.description = first_txn.description  # Update description

        await db.commit()
        await db.refresh(position)

        logger.info(
            f"Recalculated position for {isin} ({current_ticker}): "
            f"quantity={quantity}, avg_cost={average_cost}, cost_basis={cost_basis}"
        )

        return position

    @staticmethod
    async def recalculate_all_positions(db: AsyncSession) -> int:
        """
        Recalculate all positions based on current transactions.

        Handles both ISIN-based and ticker-based transactions (when ISIN is NULL).

        Args:
            db: Database session

        Returns:
            Number of positions recalculated
        """
        # Get all unique ISINs from transactions
        result = await db.execute(
            select(Transaction.isin).distinct()
        )
        isins = [row[0] for row in result.all() if row[0] is not None]

        # Get all unique tickers with NULL ISINs (ticker-only transactions)
        result_tickers = await db.execute(
            select(Transaction.ticker).where(Transaction.isin.is_(None)).distinct()
        )
        tickers_without_isin = [row[0] for row in result_tickers.all()]

        count = 0
        # Recalculate ISIN-based positions
        for isin in isins:
            position = await PositionManager.recalculate_position(db, isin=isin)
            if position:
                count += 1

        # Recalculate ticker-based positions (where ISIN is NULL)
        for ticker in tickers_without_isin:
            position = await PositionManager.recalculate_position(db, ticker=ticker)
            if position:
                count += 1

        logger.info(f"Recalculated {count} positions")
        return count

    @staticmethod
    async def detect_and_record_splits(db: AsyncSession) -> int:
        """
        Detect and record all stock splits.

        Returns:
            Number of splits detected and recorded
        """
        # Get all unique ISINs
        result = await db.execute(
            select(Transaction.isin).distinct()
        )
        isins = [row[0] for row in result.all()]

        splits_found = 0
        for isin in isins:
            split_info = await SplitDetector.detect_split(db, isin)
            if split_info:
                await SplitDetector.record_split(db, split_info)
                splits_found += 1

        logger.info(f"Detected and recorded {splits_found} stock splits")
        return splits_found

    @staticmethod
    def _determine_asset_type(ticker: str) -> AssetType:
        """
        Determine asset type from ticker symbol.

        Simple heuristic:
        - Known crypto tickers -> CRYPTO
        - Contains "ETF" or ends with ".L" -> ETF
        - Otherwise -> STOCK

        Args:
            ticker: Asset ticker symbol

        Returns:
            AssetType enum value
        """
        ticker_upper = ticker.upper()

        # Known crypto symbols
        crypto_tickers = {
            "BTC", "ETH", "USDT", "BNB", "SOL", "XRP", "ADA", "DOGE",
            "DOT", "MATIC", "SHIB", "AVAX", "LINK", "UNI", "ATOM"
        }

        if ticker_upper in crypto_tickers:
            return AssetType.CRYPTO

        # ETF indicators
        if "ETF" in ticker_upper or ticker_upper.endswith(".L"):
            return AssetType.ETF

        # Default to stock
        return AssetType.STOCK

    @staticmethod
    async def get_position_with_current_value(
        db: AsyncSession,
        identifier: str,
        current_price: Decimal
    ) -> Optional[Dict[str, Any]]:
        """
        Get position with current market value calculated.

        Args:
            db: Database session
            identifier: Asset ISIN (12 chars) or ticker symbol
            current_price: Current market price

        Returns:
            Dictionary with position data including current value and metrics
        """
        # Try ISIN first (if 12 characters)
        if len(identifier) == 12:
            result = await db.execute(
                select(Position).where(Position.isin == identifier)
            )
        else:
            # Try by current_ticker
            result = await db.execute(
                select(Position).where(Position.current_ticker == identifier)
            )

        position = result.scalar_one_or_none()

        if not position:
            return None

        current_value = position.quantity * current_price
        unrealized_gain = FinancialCalculations.calculate_unrealized_gain_loss(
            current_value, position.cost_basis
        )
        return_pct = FinancialCalculations.calculate_return_percentage(
            current_value, position.cost_basis
        )

        return {
            "ticker": position.current_ticker,
            "isin": position.isin,
            "description": position.description,
            "asset_type": position.asset_type.value,
            "quantity": position.quantity,
            "average_cost": position.average_cost,
            "cost_basis": position.cost_basis,
            "current_price": current_price,
            "current_value": current_value,
            "unrealized_gain": unrealized_gain,
            "return_percentage": return_pct,
            "last_calculated_at": position.last_calculated_at
        }
