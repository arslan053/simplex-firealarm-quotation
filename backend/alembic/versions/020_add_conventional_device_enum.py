"""Add conventional_device to selectable_category_enum

Revision ID: 020
Revises: 019
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE selectable_category_enum ADD VALUE IF NOT EXISTS 'conventional_device'")


def downgrade() -> None:
    # Postgres cannot remove enum values; no-op
    pass
