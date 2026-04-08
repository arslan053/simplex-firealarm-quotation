"""Create clients table and add client_id to projects

Revision ID: 034
Revises: 033
Create Date: 2026-04-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "034"
down_revision: Union[str, None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create clients table
    op.execute("""
        CREATE TABLE clients (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id     UUID NOT NULL REFERENCES tenants(id),
            name          TEXT NOT NULL,
            company_name  TEXT NOT NULL,
            email         TEXT,
            phone         TEXT,
            address       TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE UNIQUE INDEX uq_clients_tenant_company ON clients (tenant_id, company_name)"
    )
    op.execute("CREATE INDEX ix_clients_tenant_id ON clients (tenant_id)")

    # RLS policies
    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON clients
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON clients
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)

    # Add client_id to projects, drop client_name (now lives in clients table)
    op.execute("ALTER TABLE projects ADD COLUMN client_id UUID REFERENCES clients(id)")
    op.execute(
        "CREATE INDEX ix_projects_tenant_client ON projects (tenant_id, client_id)"
    )
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS client_name")


def downgrade() -> None:
    op.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_name TEXT NOT NULL DEFAULT ''")
    op.execute("DROP INDEX IF EXISTS ix_projects_tenant_client")
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS client_id")
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON clients")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON clients")
    op.execute("DROP TABLE IF EXISTS clients")
