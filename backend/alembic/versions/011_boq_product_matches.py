"""Add boq_product_matches table for product selection results

Revision ID: 011
Revises: 010
Create Date: 2026-03-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE boq_product_matches (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            project_id      UUID NOT NULL REFERENCES projects(id),
            boq_item_id     UUID NOT NULL REFERENCES boq_items(id) ON DELETE CASCADE,
            product_selection_id UUID REFERENCES global_product_selections(id),
            selection_kind   VARCHAR(10) NOT NULL DEFAULT 'none',
            created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_bpm_boq_item UNIQUE (boq_item_id)
        )
    """)
    op.execute(
        "CREATE INDEX ix_bpm_tenant_project ON boq_product_matches (tenant_id, project_id)"
    )

    # RLS
    op.execute("ALTER TABLE boq_product_matches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE boq_product_matches FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON boq_product_matches
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON boq_product_matches
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON boq_product_matches")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON boq_product_matches")
    op.execute("ALTER TABLE boq_product_matches DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS ix_bpm_tenant_project")
    op.execute("DROP TABLE IF EXISTS boq_product_matches")
