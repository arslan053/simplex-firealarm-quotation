"""Add status and deferred_type columns to boq_device_selections

Revision ID: 023
Revises: 022
Create Date: 2026-03-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE boq_device_selections "
        "ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'finalized'"
    )
    op.execute(
        "ALTER TABLE boq_device_selections "
        "ADD COLUMN deferred_type VARCHAR(30)"
    )
    # Backfill: existing unmatched rows → 'no_match'
    op.execute(
        "UPDATE boq_device_selections "
        "SET status = 'no_match' "
        "WHERE selectable_id IS NULL AND status = 'finalized'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE boq_device_selections DROP COLUMN IF EXISTS deferred_type")
    op.execute("ALTER TABLE boq_device_selections DROP COLUMN IF EXISTS status")
