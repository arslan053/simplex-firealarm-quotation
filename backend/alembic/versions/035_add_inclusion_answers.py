"""Add inclusion_answers JSONB column to quotations

Revision ID: 035
Revises: 034
Create Date: 2026-04-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE quotations ADD COLUMN inclusion_answers JSONB NOT NULL DEFAULT '{}';"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE quotations DROP COLUMN inclusion_answers;")
