"""Add notification_type and notification_type_auto to projects table

Stores the LLM-determined notification protocol (addressable vs
non_addressable) separately from the user's manual override,
following the same pattern as protocol/protocol_auto and
network_type/network_type_auto.

Revision ID: 031
Revises: 030
Create Date: 2026-04-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "031"
down_revision: Union[str, None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN notification_type VARCHAR(20)")
    op.execute("ALTER TABLE projects ADD COLUMN notification_type_auto VARCHAR(20)")


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS notification_type_auto")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS notification_type")
