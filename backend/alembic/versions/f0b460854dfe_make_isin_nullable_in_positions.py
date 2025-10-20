"""Make ISIN nullable in positions table

Revision ID: f0b460854dfe
Revises: f0b460854dfd
Create Date: 2025-10-20 10:15:00.000000+00:00

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
    # Make ISIN nullable in positions table
    op.alter_column('positions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=True,
                    existing_nullable=False)


def downgrade() -> None:
    # Revert ISIN to non-nullable
    op.alter_column('positions', 'isin',
                    existing_type=sa.VARCHAR(length=12),
                    nullable=False,
                    existing_nullable=True)
