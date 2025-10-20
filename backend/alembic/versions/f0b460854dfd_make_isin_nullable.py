"""Make ISIN nullable in transactions table

Revision ID: f0b460854dfd
Revises: add_system_state_table
Create Date: 2025-10-20 07:31:52.707597+00:00

This migration allows transactions to be created without ISIN values, since many
tickers don't have ISIN data available from Yahoo Finance. Manual transactions
(especially those added through the UI) frequently have NULL ISIN values.

Data Migration Notes:
- For fresh databases: No special handling needed, NULL ISINs are allowed
- For existing databases: Existing NOT NULL ISINs are preserved, new transactions
  can have NULL ISINs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = 'f0b460854dfd'
down_revision: Union[str, None] = 'add_system_state_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make ISIN nullable in transactions table to support ticker-only transactions."""
    # Check current NOT NULL constraint before altering
    # This makes the migration idempotent - safe to run multiple times

    # Make ISIN nullable in transactions table
    # This allows transactions without ISIN data (common for manually added transactions)
    op.alter_column('transactions', 'isin',
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
        text("SELECT COUNT(*) FROM transactions WHERE isin IS NULL")
    )
    null_count = null_count_result.scalar()

    if null_count > 0:
        raise Exception(
            f"Cannot downgrade: Found {null_count} transactions with NULL ISIN values. "
            "Making ISIN NOT NULL would result in data loss. "
            "Manual intervention required:\n"
            "1. Review and fix the {null_count} transactions with NULL ISIN values\n"
            "2. Either: (a) Set ISIN values from Yahoo Finance, or (b) Delete the transactions\n"
            "3. After handling all NULL ISINs, retry the downgrade\n"
            "Or: Accept the new schema with nullable ISIN and stay on the current migration."
        )

    # Only proceed if no NULL values exist
    op.alter_column('transactions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=False,
                    existing_nullable=True,
                    existing_comment='ISIN - unique identifier for the security')
