"""Add network_type column to projects

Revision ID: 024
Revises: 023
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE projects "
        "ADD COLUMN network_type VARCHAR(10)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS network_type")
