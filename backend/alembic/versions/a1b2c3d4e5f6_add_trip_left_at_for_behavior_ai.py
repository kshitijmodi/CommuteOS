"""add trip left_at for behavior ai timing-buffer signal

Revision ID: a1b2c3d4e5f6
Revises: eae11c8bfa68
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'eae11c8bfa68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('trips', sa.Column('left_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('trips', 'left_at')
