"""Add annunciator_subpanel to selectable_category_enum

Revision ID: 021
Revises: 020
Create Date: 2026-03-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE selectable_category_enum ADD VALUE IF NOT EXISTS 'annunciator_subpanel'")


def downgrade() -> None:
    # Postgres cannot remove enum values; no-op
    pass
