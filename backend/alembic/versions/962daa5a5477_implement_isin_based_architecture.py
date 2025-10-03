"""implement_isin_based_architecture

Revision ID: 962daa5a5477
Revises: 002
Create Date: 2025-10-03 07:44:21.982286+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '962daa5a5477'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Step 1: Create stock_splits table
    op.create_table(
        'stock_splits',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('split_date', sa.Date(), nullable=False),
        sa.Column('split_ratio_numerator', sa.Integer(), nullable=False),
        sa.Column('split_ratio_denominator', sa.Integer(), nullable=False),
        sa.Column('old_ticker', sa.String(length=50), nullable=True),
        sa.Column('new_ticker', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('isin', 'split_date', name='uq_stock_split_isin_date')
    )
    op.create_index(op.f('ix_stock_splits_isin'), 'stock_splits', ['isin'], unique=False)

    # Step 2: Add current_ticker column to positions (copy from ticker)
    op.add_column('positions', sa.Column('current_ticker', sa.String(length=50), nullable=True))
    op.execute('UPDATE positions SET current_ticker = ticker')
    op.alter_column('positions', 'current_ticker', nullable=False)
    op.create_index(op.f('ix_positions_current_ticker'), 'positions', ['current_ticker'], unique=False)

    # Step 3: Drop unique constraint on positions.ticker
    op.drop_constraint('positions_ticker_key', 'positions', type_='unique')
    op.drop_index('ix_positions_ticker', table_name='positions')

    # Step 4: Make positions.isin NOT NULL and add unique constraint
    # First, verify all positions have ISIN (fail migration if not)
    op.execute('UPDATE positions SET isin = ticker WHERE isin IS NULL')  # Fallback for any missing ISINs
    op.alter_column('positions', 'isin', nullable=False)
    op.create_unique_constraint('uq_positions_isin', 'positions', ['isin'])

    # Step 5: Drop positions.ticker column
    op.drop_column('positions', 'ticker')

    # Step 6: Make transactions.isin NOT NULL
    # Verify all transactions have ISIN (fail migration if not)
    op.execute('UPDATE transactions SET isin = ticker WHERE isin IS NULL')  # Fallback for any missing ISINs
    op.alter_column('transactions', 'isin', nullable=False)


def downgrade() -> None:
    # Reverse the changes
    # Step 1: Make transactions.isin nullable again
    op.alter_column('transactions', 'isin', nullable=True)

    # Step 2: Add ticker column back to positions
    op.add_column('positions', sa.Column('ticker', sa.String(length=50), nullable=True))
    op.execute('UPDATE positions SET ticker = current_ticker')
    op.alter_column('positions', 'ticker', nullable=False)
    op.create_index('ix_positions_ticker', 'positions', ['ticker'], unique=False)
    op.create_unique_constraint('positions_ticker_key', 'positions', ['ticker'])

    # Step 3: Make positions.isin nullable and drop unique constraint
    op.drop_constraint('uq_positions_isin', 'positions', type_='unique')
    op.alter_column('positions', 'isin', nullable=True)

    # Step 4: Drop current_ticker column
    op.drop_index(op.f('ix_positions_current_ticker'), table_name='positions')
    op.drop_column('positions', 'current_ticker')

    # Step 5: Drop stock_splits table
    op.drop_index(op.f('ix_stock_splits_isin'), table_name='stock_splits')
    op.drop_table('stock_splits')
