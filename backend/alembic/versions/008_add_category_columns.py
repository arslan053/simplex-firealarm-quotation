"""Add category columns to boq_items and documents

Revision ID: 008
Revises: 007
Create Date: 2026-03-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "boq_items",
        sa.Column("category", sa.String(50), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("document_category", sa.String(50), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("document_category_confidence", sa.Numeric(5, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("documents", "document_category_confidence")
    op.drop_column("documents", "document_category")
    op.drop_column("boq_items", "category")
