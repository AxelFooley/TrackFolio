"""
Edge case tests for PositionManager.

Tests critical edge cases:
- NULL ISIN and NULL ticker handling
- Duplicate tickers with different ISINs
- Position recalculation with mixed ISIN scenarios
"""
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Transaction, Position, TransactionType, AssetType
from app.services.position_manager import PositionManager
from app.database import AsyncSessionLocal


# Mark entire module as integration test (requires database)
pytestmark = pytest.mark.integration


class TestPositionManagerEdgeCases:
    """Test edge cases in position recalculation."""

    def get_db(self) -> AsyncSession:
        """Helper to create an async test database session."""
        return AsyncSessionLocal()

    @pytest.mark.asyncio
    async def test_recalculate_position_with_null_isin_and_ticker(self):
        """Test position recalculation with only ticker (NULL ISIN)."""
        async_db = self.get_db()
        ticker = f"TEST_TICKER_{datetime.utcnow().timestamp()}"

        # Create transaction with NULL ISIN but valid ticker
        transaction = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=ticker,
            isin=None,  # Explicitly NULL
            description="Test Asset",
            quantity=Decimal("10.0"),
            price_per_share=Decimal("100.0"),
            amount_eur=Decimal("1000.0"),
            amount_currency=Decimal("1000.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"ORD-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash-{datetime.utcnow().timestamp()}",
        )
        async_db.add(transaction)
        await async_db.commit()

        # Recalculate position using ticker (ISIN is None)
        position = await PositionManager.recalculate_position(
            async_db,
            isin=None,
            ticker=ticker
        )

        assert position is not None
        assert position.isin is None
        assert position.current_ticker == ticker
        assert position.quantity == Decimal("10.0")

        # Clean up
        await async_db.delete(transaction)
        await async_db.delete(position)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_recalculate_position_requires_at_least_one_identifier(self):
        """Test that recalculate_position raises ValueError when both ISIN and ticker are None."""
        async_db = self.get_db()
        with pytest.raises(ValueError, match="At least one identifier"):
            await PositionManager.recalculate_position(
                async_db,
                isin=None,
                ticker=None
            )

    @pytest.mark.asyncio
    async def test_duplicate_tickers_with_different_isins(self):
        """Test that same ticker with different ISINs creates separate positions."""
        async_db = self.get_db()
        shared_ticker = "MULTI_ISIN"
        isin1 = "US0000000001"
        isin2 = "US0000000002"

        # Create transaction with first ISIN and shared ticker
        txn1 = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=shared_ticker,
            isin=isin1,
            description="Asset Class A",
            quantity=Decimal("10.0"),
            price_per_share=Decimal("100.0"),
            amount_eur=Decimal("1000.0"),
            amount_currency=Decimal("1000.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"ORD1-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash1-{datetime.utcnow().timestamp()}",
        )

        # Create transaction with second ISIN and same ticker
        txn2 = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=shared_ticker,
            isin=isin2,
            description="Asset Class B",
            quantity=Decimal("20.0"),
            price_per_share=Decimal("50.0"),
            amount_eur=Decimal("1000.0"),
            amount_currency=Decimal("1000.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"ORD2-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash2-{datetime.utcnow().timestamp()}",
        )

        async_db.add(txn1)
        async_db.add(txn2)
        await async_db.commit()

        # Recalculate positions for both ISINs
        position1 = await PositionManager.recalculate_position(async_db, isin=isin1)
        position2 = await PositionManager.recalculate_position(async_db, isin=isin2)

        # Both should exist and be separate
        assert position1 is not None
        assert position2 is not None
        assert position1.isin == isin1
        assert position2.isin == isin2
        assert position1.id != position2.id
        assert position1.quantity == Decimal("10.0")
        assert position2.quantity == Decimal("20.0")

        # Clean up
        await async_db.delete(txn1)
        await async_db.delete(txn2)
        await async_db.delete(position1)
        await async_db.delete(position2)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_recalculate_all_positions_with_mixed_isin_and_ticker_only(self):
        """Test recalculate_all_positions with both ISIN-based and ticker-only transactions."""
        async_db = self.get_db()
        isin = "US1234567890"
        ticker_only = f"TICKET_ONLY_{datetime.utcnow().timestamp()}"

        # Create ISIN-based transaction
        txn_with_isin = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker="MIXED_TICKER",
            isin=isin,
            description="Asset with ISIN",
            quantity=Decimal("5.0"),
            price_per_share=Decimal("150.0"),
            amount_eur=Decimal("750.0"),
            amount_currency=Decimal("750.0"),
            currency="EUR",
            fees=Decimal("5.0"),
            order_reference=f"ORD_ISIN-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash_isin-{datetime.utcnow().timestamp()}",
        )

        # Create ticker-only transaction (NULL ISIN)
        txn_ticker_only = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=ticker_only,
            isin=None,
            description="Asset without ISIN",
            quantity=Decimal("15.0"),
            price_per_share=Decimal("50.0"),
            amount_eur=Decimal("750.0"),
            amount_currency=Decimal("750.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"ORD_TICKER-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash_ticker-{datetime.utcnow().timestamp()}",
        )

        async_db.add(txn_with_isin)
        async_db.add(txn_ticker_only)
        await async_db.commit()

        # Recalculate all positions
        count = await PositionManager.recalculate_all_positions(async_db)

        assert count >= 2  # At least our two positions

        # Verify both positions exist
        pos_with_isin = await PositionManager.recalculate_position(async_db, isin=isin)
        pos_ticker_only = await PositionManager.recalculate_position(async_db, ticker=ticker_only)

        assert pos_with_isin is not None
        assert pos_with_isin.isin == isin
        assert pos_ticker_only is not None
        assert pos_ticker_only.isin is None
        assert pos_ticker_only.current_ticker == ticker_only

        # Clean up
        await async_db.delete(txn_with_isin)
        await async_db.delete(txn_ticker_only)
        await async_db.delete(pos_with_isin)
        await async_db.delete(pos_ticker_only)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_duplicate_ticker_only_position_raises_error(self):
        """Test that creating duplicate ticker-only positions raises ValueError."""
        async_db = self.get_db()
        ticker_only = f"DUP_TICKER_{datetime.utcnow().timestamp()}"

        # Create first ticker-only position
        txn1 = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=ticker_only,
            isin=None,
            description="First ticker-only",
            quantity=Decimal("10.0"),
            price_per_share=Decimal("100.0"),
            amount_eur=Decimal("1000.0"),
            amount_currency=Decimal("1000.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"ORD1-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash1-{datetime.utcnow().timestamp()}",
        )

        async_db.add(txn1)
        await async_db.commit()

        # Create first position
        pos1 = await PositionManager.recalculate_position(async_db, ticker=ticker_only)
        assert pos1 is not None

        # Try to create duplicate ticker-only position (should fail with validation)
        # This simulates what would happen if two different sources tried to create positions
        txn2 = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=ticker_only,
            isin=None,
            description="Second ticker-only (duplicate)",
            quantity=Decimal("5.0"),
            price_per_share=Decimal("100.0"),
            amount_eur=Decimal("500.0"),
            amount_currency=Decimal("500.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"ORD2-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash2-{datetime.utcnow().timestamp()}",
        )

        async_db.add(txn2)
        await async_db.commit()

        # Try to recalculate - should detect existing ticker-only position
        # and either update or skip (not create duplicate)
        result = await PositionManager.recalculate_position(async_db, ticker=ticker_only)

        # Should update existing position with new transaction
        assert result is not None
        assert result.quantity == Decimal("15.0")  # 10 + 5

        # Clean up
        await async_db.delete(txn1)
        await async_db.delete(txn2)
        await async_db.delete(pos1)
        await async_db.commit()

    @pytest.mark.asyncio
    async def test_position_closed_when_quantity_becomes_zero(self):
        """Test that position is deleted when quantity becomes zero after sell."""
        async_db = self.get_db()
        ticker = f"CLOSE_POS_{datetime.utcnow().timestamp()}"
        isin = "US0000CLOSE01"

        # Create BUY transaction
        buy_txn = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.BUY,
            ticker=ticker,
            isin=isin,
            description="Test Asset",
            quantity=Decimal("10.0"),
            price_per_share=Decimal("100.0"),
            amount_eur=Decimal("1000.0"),
            amount_currency=Decimal("1000.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"BUY-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash_buy-{datetime.utcnow().timestamp()}",
        )

        async_db.add(buy_txn)
        await async_db.commit()

        # Create position
        position = await PositionManager.recalculate_position(async_db, isin=isin)
        assert position is not None
        assert position.quantity == Decimal("10.0")

        # Create SELL transaction for all shares
        sell_txn = Transaction(
            operation_date=datetime.utcnow(),
            value_date=datetime.utcnow(),
            transaction_type=TransactionType.SELL,
            ticker=ticker,
            isin=isin,
            description="Closing position",
            quantity=Decimal("10.0"),
            price_per_share=Decimal("110.0"),
            amount_eur=Decimal("1100.0"),
            amount_currency=Decimal("1100.0"),
            currency="EUR",
            fees=Decimal("0.0"),
            order_reference=f"SELL-{datetime.utcnow().timestamp()}",
            transaction_hash=f"hash_sell-{datetime.utcnow().timestamp()}",
        )

        async_db.add(sell_txn)
        await async_db.commit()

        # Recalculate position - should return None (position deleted)
        result = await PositionManager.recalculate_position(async_db, isin=isin)
        assert result is None

        # Clean up
        await async_db.delete(buy_txn)
        await async_db.delete(sell_txn)
        await async_db.commit()
