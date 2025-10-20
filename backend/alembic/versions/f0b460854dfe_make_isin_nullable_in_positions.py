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
    """Revert ISIN to non-nullable (destructive for existing NULL values)."""
    # WARNING: This will fail if there are NULL ISINs in the database
    # For safety, this downgrade requires manual intervention

    # Revert ISIN to non-nullable
    op.alter_column('positions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=False,
                    existing_nullable=True,
                    existing_comment='ISIN - unique identifier for the security (may be None for ticker-only positions)')
