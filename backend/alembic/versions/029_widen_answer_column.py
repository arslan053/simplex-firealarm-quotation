"""Widen analysis_answers.answer from varchar(10) to text

Q21 now returns a JSON array of per-item loop extractions,
which exceeds 10 characters.

Revision ID: 029
Revises: 028
Create Date: 2026-04-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE analysis_answers ALTER COLUMN answer TYPE text")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE analysis_answers ALTER COLUMN answer TYPE varchar(10)"
    )
