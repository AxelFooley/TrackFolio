"""Make ISIN nullable in transactions table

Revision ID: f0b460854dfd
Revises: add_system_state_table
Create Date: 2025-10-20 07:31:52.707597+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f0b460854dfd'
down_revision: Union[str, None] = 'add_system_state_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make ISIN nullable in transactions table
    op.alter_column('transactions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=True,
                    existing_nullable=False)


def downgrade() -> None:
    # Revert ISIN to non-nullable
    op.alter_column('transactions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=False,
                    existing_nullable=True)
