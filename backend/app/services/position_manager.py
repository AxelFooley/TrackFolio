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
    async def recalculate_position(db: AsyncSession, isin: str) -> Optional[Position]:
        """
        Recalculate position for a specific ISIN based on all transactions.

        Args:
            db: Database session
            isin: Asset ISIN (unique identifier)

        Returns:
            Updated Position object or None if no position exists
        """
        # Get all transactions for this ISIN (not ticker!)
        result = await db.execute(
            select(Transaction)
            .where(Transaction.isin == isin)
            .order_by(Transaction.operation_date)
        )
        transactions = result.scalars().all()

        if not transactions:
            # No transactions, delete position if it exists
            result = await db.execute(
                select(Position).where(Position.isin == isin)
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
            result = await db.execute(
                select(Position).where(Position.isin == isin)
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

        # Get or create position BY ISIN
        result = await db.execute(
            select(Position).where(Position.isin == isin)
        )
        position = result.scalar_one_or_none()

        # Get asset metadata from first transaction
        first_txn = transactions[0]

        # Enhanced ISIN handling for crypto assets
        final_isin = isin
        if not isin or isin.startswith("UNKNOWN-"):
            # Check if we should upgrade to a proper crypto ISIN
            from app.services.crypto_csv_parser import CryptoCSVParser
            if CryptoCSVParser.is_crypto_transaction(current_ticker):
                final_isin = CryptoCSVParser.generate_crypto_identifier(
                    current_ticker,
                    first_txn.description or current_ticker
                )
                logger.info(f"Upgraded ISIN from {isin} to {final_isin} for crypto asset {current_ticker}")

                # Update all transactions with the new ISIN
                for txn in transactions:
                    if not txn.isin or txn.isin.startswith("UNKNOWN-"):
                        txn.isin = final_isin

                isin = final_isin

        asset_type = PositionManager._determine_asset_type(current_ticker, isin)

        if position is None:
            # Create new position
            position = Position(
                isin=isin,  # ISIN is primary unique key now
                current_ticker=current_ticker,  # Changed from ticker
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

        Args:
            db: Database session

        Returns:
            Number of positions recalculated
        """
        # Get all unique ISINs from transactions (not tickers!)
        result = await db.execute(
            select(Transaction.isin).distinct()
        )
        isins = [row[0] for row in result.all()]

        count = 0
        for isin in isins:
            position = await PositionManager.recalculate_position(db, isin)
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
    def _determine_asset_type(ticker: str, isin: Optional[str] = None) -> AssetType:
        """
        Determine asset type from ticker symbol and ISIN.

        Enhanced heuristic:
        - Crypto ISIN (starts with "XC") -> CRYPTO
        - Crypto ticker detection -> CRYPTO
        - Contains "ETF" or ends with ".L" -> ETF
        - Otherwise -> STOCK

        Args:
            ticker: Asset ticker symbol
            isin: Asset ISIN (optional, helps identify crypto)

        Returns:
            AssetType enum value
        """
        if not ticker:
            logger.warning("Empty ticker provided, defaulting to STOCK")
            return AssetType.STOCK

        ticker_upper = ticker.upper().strip()

        # Check ISIN first (most reliable for crypto)
        if isin:
            isin_upper = isin.upper().strip()
            if isin_upper.startswith("XC"):
                logger.debug(f"Identified crypto asset by ISIN prefix: {isin}")
                return AssetType.CRYPTO
            elif isin_upper.startswith("UNKNOWN-"):
                logger.warning(f"Unknown ISIN format detected: {isin}, defaulting to STOCK")
                return AssetType.STOCK

        # Enhanced crypto detection using the crypto parser
        from app.services.crypto_csv_parser import CryptoCSVParser
        if CryptoCSVParser.is_crypto_transaction(ticker):
            logger.debug(f"Identified crypto asset by ticker: {ticker}")
            return AssetType.CRYPTO

        # Check for placeholder ISINs that indicate crypto
        if isin and isin.startswith("UNKNOWN-"):
            # Check if the unknown ticker might be crypto
            if CryptoCSVParser.is_crypto_transaction(ticker):
                logger.info(f"Converting unknown ISIN {isin} to crypto for ticker {ticker}")
                return AssetType.CRYPTO

        # ETF indicators
        if "ETF" in ticker_upper or ticker_upper.endswith(".L"):
            logger.debug(f"Identified ETF asset: {ticker}")
            return AssetType.ETF

        # Default to stock
        logger.debug(f"Defaulting to STOCK for ticker: {ticker}")
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
