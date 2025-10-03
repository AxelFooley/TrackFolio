"""002_remove_order_reference_unique

Revision ID: 002
Revises: 001
Create Date: 2025-10-01 15:35:00.000000

Remove unique constraint from order_reference to allow partial fills.
A single order can have multiple transactions (partial fills), so order_reference
is not unique. We rely on transaction_hash for uniqueness instead.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove unique constraint from order_reference."""
    # Drop the unique constraint on order_reference
    op.drop_constraint('transactions_order_reference_key', 'transactions', type_='unique')

    # Keep the index for performance, but make it non-unique
    # The index was already created as unique, so we need to recreate it as non-unique
    op.drop_index('ix_transactions_order_reference', table_name='transactions')
    op.create_index('ix_transactions_order_reference', 'transactions', ['order_reference'], unique=False)


def downgrade() -> None:
    """Restore unique constraint on order_reference."""
    op.drop_index('ix_transactions_order_reference', table_name='transactions')
    op.create_index('ix_transactions_order_reference', 'transactions', ['order_reference'], unique=True)
    op.create_unique_constraint('transactions_order_reference_key', 'transactions', ['order_reference'])
