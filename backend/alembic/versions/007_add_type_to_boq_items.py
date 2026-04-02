"""Add type column to boq_items

Revision ID: 007
Revises: 006
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "boq_items",
        sa.Column("type", sa.String(20), nullable=False, server_default="boq_item"),
    )


def downgrade() -> None:
    op.drop_column("boq_items", "type")
