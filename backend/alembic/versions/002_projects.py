"""Add projects table with RLS

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("project_name", sa.Text(), nullable=False),
        sa.Column("client_name", sa.Text(), nullable=False),
        sa.Column(
            "country", sa.String(100), nullable=False, server_default="KSA"
        ),
        sa.Column("city", sa.String(200), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("panel_family", sa.String(200), nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="IN_PROGRESS",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])
    op.create_index(
        "ix_projects_tenant_owner", "projects", ["tenant_id", "owner_user_id"]
    )
    op.create_index(
        "ix_projects_tenant_created", "projects", ["tenant_id", "created_at"]
    )

    # --- RLS policies for tenant isolation ---
    op.execute("ALTER TABLE projects ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE projects FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON projects
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    # App-bypass policy: when no session var is set (e.g. migrations, seeds),
    # allow full access. The app ALWAYS sets the var for tenant requests.
    op.execute(
        """
        CREATE POLICY app_bypass_policy ON projects
            USING (current_setting('app.tenant_id', true) IS NULL)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON projects")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON projects")
    op.execute("ALTER TABLE projects DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_projects_tenant_created")
    op.drop_index("ix_projects_tenant_owner")
    op.drop_index("ix_projects_tenant_id")
    op.drop_table("projects")
