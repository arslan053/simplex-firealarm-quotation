"""Add subject column to quotations

Revision ID: 033
Revises: 032
Create Date: 2026-04-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE quotations ADD COLUMN subject TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE quotations DROP COLUMN IF EXISTS subject")
