"""Add subcategory column to selectables

Revision ID: 022
Revises: 021
Create Date: 2026-03-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE selectables ADD COLUMN subcategory TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE selectables DROP COLUMN IF EXISTS subcategory")
