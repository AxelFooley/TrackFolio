"""004_add_crypto_paper_portfolio_models

Revision ID: 004
Revises: 962daa5a5477
Create Date: 2025-10-07 00:00:00.000000

Add crypto paper wallet portfolio and transaction models.
Creates crypto_paper_portfolios and crypto_paper_transactions tables
for tracking crypto paper wallet holdings separate from stock portfolios.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '962daa5a5477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create crypto paper wallet tables."""

    # Create crypto_paper_portfolios table
    op.create_table(
        'crypto_paper_portfolios',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_crypto_paper_portfolios_user_id', 'crypto_paper_portfolios', ['user_id'])

    # Create crypto_paper_transactions table
    op.create_table(
        'crypto_paper_transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('coingecko_id', sa.String(length=100), nullable=True),
        sa.Column('transaction_type', sa.String(length=15), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('price_at_execution', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('fee', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['portfolio_id'], ['crypto_paper_portfolios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for crypto_paper_transactions
    op.create_index('ix_crypto_paper_transactions_portfolio_id', 'crypto_paper_transactions', ['portfolio_id'])
    op.create_index('ix_crypto_paper_transactions_symbol', 'crypto_paper_transactions', ['symbol'])
    op.create_index('ix_crypto_paper_transactions_coingecko_id', 'crypto_paper_transactions', ['coingecko_id'])
    op.create_index('ix_crypto_paper_transactions_transaction_type', 'crypto_paper_transactions', ['transaction_type'])
    op.create_index('ix_crypto_paper_transactions_timestamp', 'crypto_paper_transactions', ['timestamp'])
    op.create_index('ix_crypto_transactions_portfolio_symbol', 'crypto_paper_transactions', ['portfolio_id', 'symbol'])
    op.create_index('ix_crypto_transactions_portfolio_type', 'crypto_paper_transactions', ['portfolio_id', 'transaction_type'])
    op.create_index('ix_crypto_transactions_symbol_date', 'crypto_paper_transactions', ['symbol', 'timestamp'])
    op.create_index('ix_crypto_transactions_type_date', 'crypto_paper_transactions', ['transaction_type', 'timestamp'])


def downgrade() -> None:
    """Drop crypto paper wallet tables."""
    op.drop_table('crypto_paper_transactions')
    op.drop_table('crypto_paper_portfolios')