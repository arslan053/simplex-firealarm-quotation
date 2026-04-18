"""Add name column to users table

Revision ID: 038
Revises: 037
Create Date: 2026-04-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN name VARCHAR(200);")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN name;")
