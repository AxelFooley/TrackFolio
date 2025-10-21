"""Add unique index on ticker for ticker-only positions

Revision ID: add_ticker_uniqueness
Revises: f0b460854dfe
Create Date: 2025-10-20 11:00:00.000000+00:00

This migration adds a partial unique index on positions.current_ticker where ISIN is NULL.
This ensures that ticker-only positions (those without ISIN) are unique by ticker.

Requirements:
- Must run AFTER f0b460854dfe (positions ISIN nullable)
- Enforces uniqueness of ticker for positions without ISIN

Data Integrity:
- Positions with ISIN values can still have multiple instances (one per ISIN)
- Positions without ISIN must have unique ticker values
- If duplicate ticker-only positions exist, this migration will fail and manual cleanup is required

Safe to run multiple times (idempotent):
- Using CREATE INDEX IF NOT EXISTS
- Safe on both fresh and existing databases
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'add_ticker_uniqueness'
down_revision: Union[str, None] = 'f0b460854dfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add partial unique index on ticker for ticker-only positions."""
    # Create a partial unique index that only applies to positions without ISIN
    # This ensures each ticker can only have one position when ISIN is NULL
    # Multiple positions with the same ticker are allowed if they have different ISINs
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_position_ticker_only
        ON positions(current_ticker)
        WHERE isin IS NULL;
        """
    )


def downgrade() -> None:
    """Remove the partial unique index on ticker."""
    # Safe to drop - just removes the uniqueness constraint for ticker-only positions
    op.execute(
        """
        DROP INDEX IF EXISTS idx_position_ticker_only;
        """
    )
