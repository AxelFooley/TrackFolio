"""Make ISIN nullable in positions table

Revision ID: f0b460854dfe
Revises: f0b460854dfd
Create Date: 2025-10-20 10:15:00.000000+00:00

This migration allows positions to be created for assets without ISIN data.
Positions are now identified by either ISIN (if available) or ticker symbol.

Requirements:
- Must run AFTER f0b460854dfd (transactions ISIN nullable)
- This ensures consistency: if transactions can have NULL ISIN, positions must too

Data Migration Notes:
- For fresh databases: No special handling needed
- For existing databases: Positions are uniquely identified by ISIN if present,
  otherwise by ticker. The UNIQUE constraint on ISIN is preserved to allow
  multiple NULL values for ticker-only positions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'f0b460854dfe'
down_revision: Union[str, None] = 'f0b460854dfd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make ISIN nullable in positions table to support ticker-only positions."""
    # Make ISIN nullable in positions table
    # This allows positions without ISIN data (common for manually added transactions)
    # The UNIQUE constraint remains but allows multiple NULL values
    op.alter_column('positions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=True,
                    existing_nullable=False,
                    existing_comment='ISIN - unique identifier for the security')


def downgrade() -> None:
    """Revert ISIN to non-nullable with safety checks.

    This downgrade function includes safety checks to prevent data loss.
    If NULL values exist in the ISIN column, the downgrade will fail with
    an informative error message.
    """
    # Safety check: Count NULL ISIN values
    connection = op.get_bind()
    null_count_result = connection.execute(
        text("SELECT COUNT(*) FROM positions WHERE isin IS NULL")
    )
    null_count = null_count_result.scalar()

    if null_count > 0:
        raise Exception(
            f"Cannot downgrade: Found {null_count} positions with NULL ISIN values. "
            "Making ISIN NOT NULL would result in data loss. "
            "Manual intervention required:\n"
            "1. Review and fix the {null_count} positions with NULL ISIN values\n"
            "2. Either: (a) Set ISIN values from Yahoo Finance for the associated transactions, or (b) Delete the positions and their transactions\n"
            "3. After handling all NULL ISINs, retry the downgrade\n"
            "Or: Accept the new schema with nullable ISIN and stay on the current migration."
        )

    # Only proceed if no NULL values exist
    op.alter_column('positions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=False,
                    existing_nullable=True,
                    existing_comment='ISIN - unique identifier for the security')
