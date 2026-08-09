"""add chat_messages.shown_headsigns for real "other direction" follow-ups

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('chat_messages', sa.Column('shown_headsigns', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('chat_messages', 'shown_headsigns')
