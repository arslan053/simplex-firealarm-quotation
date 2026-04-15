"""Create tenant_settings table

Revision ID: 037
Revises: 036
Create Date: 2026-04-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "037"
down_revision: Union[str, None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tenant_settings (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            settings JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            UNIQUE (tenant_id)
        );
    """)

    # RLS policies
    op.execute(
        "ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY;"
    )
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON tenant_settings
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON tenant_settings
            USING (
                current_setting('app.current_tenant_id', true) IS NULL
                OR current_setting('app.current_tenant_id', true) = ''
            );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_settings;")
