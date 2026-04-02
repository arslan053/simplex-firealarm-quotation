"""Add panel_groups table and panel_group_id FK on panel_selections

Revision ID: 025
Revises: 024
Create Date: 2026-03-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── panel_groups table ──
    op.execute("""
        CREATE TABLE panel_groups (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id),
            project_id  UUID NOT NULL REFERENCES projects(id),
            boq_item_id UUID REFERENCES boq_items(id) ON DELETE SET NULL,
            description TEXT,
            loop_count  INTEGER NOT NULL,
            quantity    INTEGER NOT NULL DEFAULT 1,
            panel_type  VARCHAR(20),
            is_main     BOOLEAN NOT NULL DEFAULT false,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX ix_panel_groups_project ON panel_groups (tenant_id, project_id)"
    )

    # RLS
    op.execute("ALTER TABLE panel_groups ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE panel_groups FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON panel_groups
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON panel_groups
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)

    # ── Add panel_group_id FK to panel_selections ──
    op.execute("""
        ALTER TABLE panel_selections
        ADD COLUMN panel_group_id UUID REFERENCES panel_groups(id) ON DELETE SET NULL
    """)


def downgrade() -> None:
    # Drop FK column from panel_selections
    op.execute("ALTER TABLE panel_selections DROP COLUMN IF EXISTS panel_group_id")

    # Drop panel_groups table
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON panel_groups")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON panel_groups")
    op.execute("ALTER TABLE panel_groups DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS ix_panel_groups_project")
    op.execute("DROP TABLE IF EXISTS panel_groups")
