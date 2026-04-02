"""Add panel_selections table for 4007 panel configuration

Revision ID: 017
Revises: 016
Create Date: 2026-03-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE panel_selections (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            project_id      UUID NOT NULL REFERENCES projects(id),
            product_code    VARCHAR(20) NOT NULL,
            product_name    TEXT,
            quantity        INTEGER NOT NULL DEFAULT 1,
            source          VARCHAR(50) NOT NULL,
            question_no     INTEGER,
            reason          TEXT,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX ix_panel_sel_tenant_project ON panel_selections (tenant_id, project_id)"
    )

    # RLS
    op.execute("ALTER TABLE panel_selections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE panel_selections FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON panel_selections
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON panel_selections
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON panel_selections")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON panel_selections")
    op.execute("ALTER TABLE panel_selections DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS ix_panel_sel_tenant_project")
    op.execute("DROP TABLE IF EXISTS panel_selections")
