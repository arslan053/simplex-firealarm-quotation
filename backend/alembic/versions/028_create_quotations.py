"""Create quotations table

Revision ID: 028
Revises: 027
Create Date: 2026-04-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE quotations (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            project_id          UUID NOT NULL REFERENCES projects(id),
            generated_by_user_id UUID NOT NULL REFERENCES users(id),

            client_name         TEXT NOT NULL,
            client_address      TEXT NOT NULL,
            service_option      INTEGER NOT NULL DEFAULT 1,
            advance_percent     NUMERIC(5,2) NOT NULL DEFAULT 25.00,
            delivery_percent    NUMERIC(5,2) NOT NULL DEFAULT 70.00,
            completion_percent  NUMERIC(5,2) NOT NULL DEFAULT 5.00,
            margin_percent      NUMERIC(5,2) NOT NULL DEFAULT 0.00,

            reference_number    TEXT NOT NULL,
            subtotal_sar        NUMERIC(15,2) NOT NULL,
            vat_sar             NUMERIC(15,2) NOT NULL,
            grand_total_sar     NUMERIC(15,2) NOT NULL,

            object_key          TEXT NOT NULL,
            original_file_name  TEXT NOT NULL,
            file_size           BIGINT,

            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_quotations_project "
        "ON quotations (tenant_id, project_id)"
    )

    # RLS
    op.execute("ALTER TABLE quotations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE quotations FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON quotations
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON quotations
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON quotations")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON quotations")
    op.execute("ALTER TABLE quotations DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS uq_quotations_project")
    op.execute("DROP TABLE IF EXISTS quotations")
