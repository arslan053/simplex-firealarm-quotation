"""Add reason column to boq_device_selections

Revision ID: 016
Revises: 015
Create Date: 2026-03-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE boq_device_selections ADD COLUMN reason TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE boq_device_selections DROP COLUMN reason")
