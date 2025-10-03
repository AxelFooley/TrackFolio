#!/usr/bin/env python3
"""
Migrate existing data to ISIN-based architecture.

This script should be run AFTER running Alembic migrations:
1. ./venv/bin/alembic upgrade head
2. ./venv/bin/python migrate_to_isin.py

What it does:
- Recalculates all positions grouped by ISIN (not ticker)
- Detects and records stock splits
- Verifies TSLA position is correct (0 shares after 1:3 split)
"""
import asyncio
import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.database import AsyncSessionLocal
from app.services.position_manager import PositionManager
from app.models import Position, StockSplit
from sqlalchemy import select
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate():
    """Run the ISIN-based migration."""

    print("\n" + "="*80)
    print("ISIN-BASED ARCHITECTURE MIGRATION")
    print("="*80 + "\n")

    async with AsyncSessionLocal() as db:
        # Step 1: Recalculate all positions by ISIN
        print("Step 1: Recalculating all positions by ISIN...")
        print("-" * 80)

        count = await PositionManager.recalculate_all_positions(db)
        print(f"✓ Recalculated {count} positions\n")

        # Step 2: Detect and record stock splits
        print("Step 2: Detecting stock splits...")
        print("-" * 80)

        splits = await PositionManager.detect_and_record_splits(db)
        print(f"✓ Detected and recorded {splits} stock splits\n")

        # Step 3: Display split details
        if splits > 0:
            print("Step 3: Split Details:")
            print("-" * 80)

            result = await db.execute(
                select(StockSplit).order_by(StockSplit.split_date)
            )
            split_records = result.scalars().all()

            for split in split_records:
                print(f"  • {split.isin}: {split.old_ticker} → {split.new_ticker}")
                print(f"    Ratio: {split.split_ratio_numerator}:{split.split_ratio_denominator}")
                print(f"    Date: {split.split_date}")
                print()

        # Step 4: Verify TSLA position (should be 0 after split)
        print("Step 4: Verifying TSLA position...")
        print("-" * 80)

        result = await db.execute(
            select(Position).where(Position.isin == 'US88160R1014')
        )
        tsla_position = result.scalar_one_or_none()

        if tsla_position:
            print(f"  TSLA Position Found:")
            print(f"  • ISIN: {tsla_position.isin}")
            print(f"  • Current Ticker: {tsla_position.current_ticker}")
            print(f"  • Quantity: {tsla_position.quantity}")
            print(f"  • Cost Basis: €{tsla_position.cost_basis}")

            if tsla_position.quantity == 0:
                print(f"  ✓ TSLA position correctly shows 0 shares (after 1:3 split)")
            else:
                print(f"  ⚠ Expected 0 shares, got {tsla_position.quantity}")
        else:
            print(f"  ✓ TSLA position removed (quantity was 0)")

        print()

        # Step 5: Show all positions
        print("Step 5: All Positions (grouped by ISIN):")
        print("-" * 80)

        result = await db.execute(
            select(Position).order_by(Position.current_ticker)
        )
        positions = result.scalars().all()

        for pos in positions:
            print(f"  {pos.current_ticker:10s} | ISIN: {pos.isin} | {pos.quantity:>10.2f} shares")

        print()
        print("="*80)
        print("MIGRATION COMPLETE!")
        print("="*80)
        print()
        print("Next steps:")
        print("  1. Verify positions are correct")
        print("  2. Test CSV import with new ISIN validation")
        print("  3. Check split detection works correctly")
        print("  4. Update frontend to display ISIN and splits")
        print()


if __name__ == "__main__":
    asyncio.run(migrate())
