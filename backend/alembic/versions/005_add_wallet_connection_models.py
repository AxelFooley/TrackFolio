"""005_add_wallet_connection_models

Revision ID: 005
Revises: 004
Create Date: 2025-10-07 15:30:00.000000

Add wallet connection models for crypto portfolio tracking.
Creates wallet_connections, wallet_addresses, and wallet_sync_statuses tables
to support multiple wallet connection types and blockchain networks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create wallet connection tables."""

    # Create wallet_connections table
    op.create_table(
        'wallet_connections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('portfolio_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('connection_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=15), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('network', sa.String(length=15), nullable=False),
        sa.Column('encrypted_credentials', sa.Text(), nullable=True),
        sa.Column('public_key', sa.String(length=255), nullable=True),
        sa.Column('address_validation_hash', sa.String(length=255), nullable=True),
        sa.Column('auto_sync_enabled', sa.Boolean(), nullable=False),
        sa.Column('sync_frequency_minutes', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['portfolio_id'], ['crypto_paper_portfolios.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for wallet_connections
    op.create_index('ix_wallet_connections_portfolio_id', 'wallet_connections', ['portfolio_id'])
    op.create_index('ix_wallet_connections_connection_type', 'wallet_connections', ['connection_type'])
    op.create_index('ix_wallet_connections_status', 'wallet_connections', ['status'])
    op.create_index('ix_wallet_connections_network', 'wallet_connections', ['network'])
    op.create_index('ix_wallet_connections_public_key', 'wallet_connections', ['public_key'])
    op.create_index('ix_wallet_connections_portfolio_type', 'wallet_connections', ['portfolio_id', 'connection_type'])
    op.create_index('ix_wallet_connections_network_status', 'wallet_connections', ['network', 'status'])
    op.create_index('ix_wallet_connections_provider_type', 'wallet_connections', ['provider', 'connection_type'])

    # Create wallet_addresses table
    op.create_table(
        'wallet_addresses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('wallet_connection_id', sa.Integer(), nullable=False),
        sa.Column('address', sa.String(length=255), nullable=False),
        sa.Column('address_label', sa.String(length=100), nullable=True),
        sa.Column('network', sa.String(length=15), nullable=False),
        sa.Column('is_valid', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('balance_satoshi', sa.Integer(), nullable=True),
        sa.Column('last_transaction_hash', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('last_sync_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['wallet_connection_id'], ['wallet_connections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for wallet_addresses
    op.create_index('ix_wallet_addresses_wallet_connection_id', 'wallet_addresses', ['wallet_connection_id'])
    op.create_index('ix_wallet_addresses_address', 'wallet_addresses', ['address'])
    op.create_index('ix_wallet_addresses_network', 'wallet_addresses', ['network'])
    op.create_index('ix_wallet_addresses_connection_address', 'wallet_addresses', ['wallet_connection_id', 'address'])
    op.create_index('ix_wallet_addresses_network_active', 'wallet_addresses', ['network', 'is_active'])
    op.create_index('ix_wallet_addresses_address_valid', 'wallet_addresses', ['address', 'is_valid'])

    # Create wallet_sync_statuses table
    op.create_table(
        'wallet_sync_statuses',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('wallet_connection_id', sa.Integer(), nullable=False),
        sa.Column('sync_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=15), nullable=False),
        sa.Column('transactions_found', sa.Integer(), nullable=False),
        sa.Column('transactions_processed', sa.Integer(), nullable=False),
        sa.Column('new_transactions', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('sync_metadata', sa.Text(), nullable=True),
        sa.Column('triggered_by', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['wallet_connection_id'], ['wallet_connections.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for wallet_sync_statuses
    op.create_index('ix_wallet_sync_statuses_wallet_connection_id', 'wallet_sync_statuses', ['wallet_connection_id'])
    op.create_index('ix_wallet_sync_statuses_sync_type', 'wallet_sync_statuses', ['sync_type'])
    op.create_index('ix_wallet_sync_statuses_status', 'wallet_sync_statuses', ['status'])
    op.create_index('ix_wallet_sync_statuses_started_at', 'wallet_sync_statuses', ['started_at'])
    op.create_index('ix_wallet_sync_statuses_connection_status', 'wallet_sync_statuses', ['wallet_connection_id', 'status'])
    op.create_index('ix_wallet_sync_statuses_type_started', 'wallet_sync_statuses', ['sync_type', 'started_at'])
    op.create_index('ix_wallet_sync_statuses_started_desc', 'wallet_sync_statuses', ['started_at'])


def downgrade() -> None:
    """Drop wallet connection tables."""
    op.drop_table('wallet_sync_statuses')
    op.drop_table('wallet_addresses')
    op.drop_table('wallet_connections')