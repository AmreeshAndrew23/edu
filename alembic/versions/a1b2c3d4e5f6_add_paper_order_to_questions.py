"""add paper_order to questions

Revision ID: a1b2c3d4e5f6
Revises: d3a1cef9ae36
Create Date: 2026-06-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd3a1cef9ae36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('questions', sa.Column('paper_order', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('questions', 'paper_order')
