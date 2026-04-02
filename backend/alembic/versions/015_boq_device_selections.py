"""Add boq_device_selections table for LLM-driven device matching

Revision ID: 015
Revises: 014
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE boq_device_selections (
            id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               UUID NOT NULL REFERENCES tenants(id),
            project_id              UUID NOT NULL REFERENCES projects(id),
            boq_item_id             UUID NOT NULL REFERENCES boq_items(id) ON DELETE CASCADE,
            selectable_id           UUID REFERENCES selectables(id),
            selection_type          VARCHAR(10) NOT NULL DEFAULT 'none',
            product_codes           TEXT[],
            product_descriptions    TEXT[],
            created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_bds_boq_item UNIQUE (boq_item_id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_bds_tenant_project ON boq_device_selections (tenant_id, project_id)"
    )

    # RLS
    op.execute("ALTER TABLE boq_device_selections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE boq_device_selections FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON boq_device_selections
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON boq_device_selections
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON boq_device_selections")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON boq_device_selections")
    op.execute("ALTER TABLE boq_device_selections DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS ix_bds_tenant_project")
    op.execute("DROP TABLE IF EXISTS boq_device_selections")
