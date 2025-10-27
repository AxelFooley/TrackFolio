"""Add composite index for crypto_portfolio_snapshots performance optimization

This migration adds a composite index on (snapshot_date, base_currency) to improve
query performance when filtering snapshots by date and aggregating by currency.

Used by: portfolio_aggregator.py get_unified_performance() method
Impact: Faster snapshot filtering and currency-based aggregation

Revision ID: 001_composite_index
Revises: f0b460854dfe
Create Date: 2025-10-27 10:00:00+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001_composite_index'
down_revision: Union[str, None] = 'f0b460854dfe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create composite index for performance optimization."""
    op.create_index(
        'ix_crypto_portfolio_snapshots_date_currency',
        'crypto_portfolio_snapshots',
        ['snapshot_date', 'base_currency'],
        unique=False
    )


def downgrade() -> None:
    """Remove composite index."""
    op.drop_index(
        'ix_crypto_portfolio_snapshots_date_currency',
        table_name='crypto_portfolio_snapshots'
    )
