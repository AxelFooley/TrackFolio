"""001_initial_schema

Revision ID: 001
Revises:
Create Date: 2025-10-01 00:00:00.000000

Initial database schema for Portfolio Tracker.
Creates all tables based on PRD Section 6 - Database Schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('operation_date', sa.Date(), nullable=False),
        sa.Column('value_date', sa.Date(), nullable=False),
        sa.Column('transaction_type', sa.String(length=10), nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('price_per_share', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('amount_eur', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('amount_currency', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR'),
        sa.Column('fees', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('order_reference', sa.String(length=100), nullable=False),
        sa.Column('transaction_hash', sa.String(length=64), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_reference'),
        sa.UniqueConstraint('transaction_hash')
    )
    op.create_index('ix_transactions_operation_date', 'transactions', ['operation_date'])
    op.create_index('ix_transactions_order_reference', 'transactions', ['order_reference'], unique=True)
    op.create_index('ix_transactions_ticker', 'transactions', ['ticker'])
    op.create_index('ix_transactions_ticker_date', 'transactions', ['ticker', 'operation_date'])
    op.create_index('ix_transactions_transaction_hash', 'transactions', ['transaction_hash'], unique=True)
    op.create_index('ix_transactions_type_date', 'transactions', ['transaction_type', 'operation_date'])

    # Create positions table
    op.create_table(
        'positions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('asset_type', sa.String(length=10), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('average_cost', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('cost_basis', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('last_calculated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker')
    )
    op.create_index('ix_positions_ticker', 'positions', ['ticker'], unique=True)

    # Create price_history table
    op.create_table(
        'price_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('open', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('high', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('low', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('close', sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column('volume', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker', 'date', name='uix_ticker_date')
    )
    op.create_index('ix_price_history_date', 'price_history', ['date'])
    op.create_index('ix_price_history_ticker', 'price_history', ['ticker'])
    op.create_index('ix_price_history_ticker_date', 'price_history', ['ticker', 'date'])

    # Create benchmark table
    op.create_table(
        'benchmark',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('ticker', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create portfolio_snapshots table
    op.create_table(
        'portfolio_snapshots',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('snapshot_date', sa.Date(), nullable=False),
        sa.Column('total_value', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('total_cost_basis', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='EUR'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('snapshot_date', name='uix_snapshot_date')
    )
    op.create_index('ix_portfolio_snapshots_snapshot_date', 'portfolio_snapshots', ['snapshot_date'], unique=True)

    # Create cached_metrics table
    op.create_table(
        'cached_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('metric_key', sa.String(length=100), nullable=False),
        sa.Column('metric_value', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('metric_type', 'metric_key', name='uix_metric_type_key')
    )
    op.create_index('ix_cached_metrics_expires', 'cached_metrics', ['expires_at'])
    op.create_index('ix_cached_metrics_metric_key', 'cached_metrics', ['metric_key'])
    op.create_index('ix_cached_metrics_metric_type', 'cached_metrics', ['metric_type'])
    op.create_index('ix_cached_metrics_type_key', 'cached_metrics', ['metric_type', 'metric_key'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('cached_metrics')
    op.drop_table('portfolio_snapshots')
    op.drop_table('benchmark')
    op.drop_table('price_history')
    op.drop_table('positions')
    op.drop_table('transactions')
