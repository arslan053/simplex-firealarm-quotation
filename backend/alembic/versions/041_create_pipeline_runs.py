"""Create pipeline_runs table and add quotation_config to projects

Revision ID: 041
Revises: 040
Create Date: 2026-04-20 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "041"
down_revision: Union[str, None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -- pipeline_runs table --
    op.execute("""
        CREATE TABLE pipeline_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id),
            project_id UUID NOT NULL REFERENCES projects(id),
            user_id UUID NOT NULL REFERENCES users(id),
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            current_step VARCHAR(30),
            steps_completed JSONB NOT NULL DEFAULT '[]',
            error_message TEXT,
            error_step VARCHAR(30),
            retry_count INTEGER NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX ix_pipeline_runs_project ON pipeline_runs (tenant_id, project_id)"
    )

    # RLS policies
    op.execute("ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON pipeline_runs
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON pipeline_runs
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)

    # -- quotation_config JSONB column on projects --
    op.execute(
        "ALTER TABLE projects ADD COLUMN quotation_config JSONB"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE projects DROP COLUMN IF EXISTS quotation_config")
    op.execute("DROP TABLE IF EXISTS pipeline_runs")
