"""Add retry columns to subscriptions for auto-renewal

Revision ID: 040
Revises: 039
Create Date: 2026-04-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "040"
down_revision: Union[str, None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE subscriptions ADD COLUMN renewal_attempts INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE subscriptions ADD COLUMN next_retry_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE subscriptions ADD COLUMN renewal_failed_at TIMESTAMPTZ"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS renewal_failed_at")
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS next_retry_at")
    op.execute("ALTER TABLE subscriptions DROP COLUMN IF EXISTS renewal_attempts")
