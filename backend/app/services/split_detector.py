"""
Stock split detection service.

Analyzes transaction patterns to detect stock splits.
"""
from datetime import date
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.models import Transaction, StockSplit

logger = logging.getLogger(__name__)


class SplitDetector:
    """Detect stock splits from transaction patterns."""

    # Common split ratios to detect
    COMMON_RATIOS = {
        0.5: (1, 2),    # 1:2 split
        0.33: (1, 3),   # 1:3 split
        0.25: (1, 4),   # 1:4 split
        0.2: (1, 5),    # 1:5 split
        0.1: (1, 10),   # 1:10 split
        2.0: (2, 1),    # 2:1 reverse split
        3.0: (3, 1),    # 3:1 reverse split
        4.0: (4, 1),    # 4:1 reverse split
        5.0: (5, 1),    # 5:1 reverse split
        10.0: (10, 1),  # 10:1 reverse split
    }

    @staticmethod
    async def detect_split(
        db: AsyncSession,
        isin: str
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if a stock split occurred for given ISIN.

        Analyzes:
        1. Multiple tickers for same ISIN
        2. Price ratio between old and new ticker
        3. Matches against common split ratios

        Args:
            db: Database session
            isin: ISIN to analyze

        Returns:
            Split info dict or None if no split detected
        """
        # Get all transactions for this ISIN
        result = await db.execute(
            select(Transaction)
            .where(Transaction.isin == isin)
            .order_by(Transaction.operation_date)
        )
        transactions = result.scalars().all()

        if len(transactions) < 2:
            return None

        # Group by ticker
        tickers = list(set(t.ticker for t in transactions))

        if len(tickers) < 2:
            # No ticker change, no split
            return None

        # Assume first ticker is old, last is new
        old_ticker = tickers[0]
        new_ticker = tickers[-1]

        old_txns = [t for t in transactions if t.ticker == old_ticker]
        new_txns = [t for t in transactions if t.ticker == new_ticker]

        if not old_txns or not new_txns:
            return None

        # Calculate average prices
        avg_old_price = sum(t.price_per_share for t in old_txns) / len(old_txns)
        avg_new_price = sum(t.price_per_share for t in new_txns) / len(new_txns)

        if avg_new_price == 0:
            return None

        # Calculate ratio
        price_ratio = float(avg_old_price / avg_new_price)

        # Match against common ratios (with 15% tolerance)
        for expected_ratio, (num, denom) in SplitDetector.COMMON_RATIOS.items():
            if abs(price_ratio - expected_ratio) / expected_ratio < 0.15:
                split_date = new_txns[0].operation_date

                logger.info(
                    f"Split detected for {isin}: {old_ticker} -> {new_ticker}, "
                    f"ratio {num}:{denom}, date {split_date}"
                )

                return {
                    "isin": isin,
                    "split_date": split_date,
                    "split_ratio_numerator": num,
                    "split_ratio_denominator": denom,
                    "old_ticker": old_ticker,
                    "new_ticker": new_ticker,
                    "price_ratio": price_ratio
                }

        logger.warning(
            f"Ticker change detected for {isin} ({old_ticker} -> {new_ticker}) "
            f"but ratio {price_ratio:.2f} doesn't match common splits"
        )
        return None

    @staticmethod
    async def record_split(
        db: AsyncSession,
        split_info: Dict[str, Any]
    ) -> StockSplit:
        """
        Record a detected split in the database.

        Args:
            db: Database session
            split_info: Split information dict

        Returns:
            Created StockSplit record
        """
        # Check if already exists
        result = await db.execute(
            select(StockSplit)
            .where(
                StockSplit.isin == split_info["isin"],
                StockSplit.split_date == split_info["split_date"]
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Split already recorded: {existing}")
            return existing

        # Create new split record
        split = StockSplit(
            isin=split_info["isin"],
            split_date=split_info["split_date"],
            split_ratio_numerator=split_info["split_ratio_numerator"],
            split_ratio_denominator=split_info["split_ratio_denominator"],
            old_ticker=split_info["old_ticker"],
            new_ticker=split_info["new_ticker"]
        )

        db.add(split)
        await db.commit()
        await db.refresh(split)

        logger.info(f"Recorded split: {split}")
        return split
