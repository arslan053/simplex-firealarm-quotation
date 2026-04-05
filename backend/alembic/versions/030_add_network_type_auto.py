"""Add network_type_auto column to projects table

Tracks the AI-determined network type separately from the manual override
(network_type), following the same pattern as protocol / protocol_auto.

Revision ID: 030
Revises: 029
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "030"
down_revision: Union[str, None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN network_type_auto VARCHAR(10)")
    # Backfill: copy existing network_type into network_type_auto
    op.execute("UPDATE projects SET network_type_auto = network_type WHERE network_type IS NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS network_type_auto")
