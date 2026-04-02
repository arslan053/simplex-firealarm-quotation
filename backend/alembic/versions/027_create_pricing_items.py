"""Create pricing_items table

Revision ID: 027
Revises: 026
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE pricing_items (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            project_id      UUID NOT NULL REFERENCES projects(id),
            section         VARCHAR(20) NOT NULL,
            row_number      INTEGER NOT NULL,
            description     TEXT,
            quantity        NUMERIC(15,4) NOT NULL,
            unit_cost_sar   NUMERIC(15,2) NOT NULL,
            total_sar       NUMERIC(15,2) NOT NULL,
            product_details JSONB NOT NULL DEFAULT '[]',
            source_id       UUID,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX ix_pricing_items_project ON pricing_items (tenant_id, project_id)"
    )

    # RLS
    op.execute("ALTER TABLE pricing_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pricing_items FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON pricing_items
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON pricing_items
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON pricing_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON pricing_items")
    op.execute("ALTER TABLE pricing_items DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS ix_pricing_items_project")
    op.execute("DROP TABLE IF EXISTS pricing_items")
