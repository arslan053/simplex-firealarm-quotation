"""Add documents and boq_items tables with RLS

Revision ID: 003
Revises: 002
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- documents table ---
    op.create_table(
        "documents",
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
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by_user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("type", sa.String(20), nullable=False, server_default="BOQ"),
        sa.Column("original_file_name", sa.Text(), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
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
    op.create_index("ix_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index(
        "ix_documents_tenant_project", "documents", ["tenant_id", "project_id"]
    )

    # RLS for documents
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON documents
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY app_bypass_policy ON documents
            USING (current_setting('app.tenant_id', true) IS NULL)
        """
    )

    # --- boq_items table ---
    op.create_table(
        "boq_items",
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
            "project_id",
            UUID(as_uuid=True),
            sa.ForeignKey("projects.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=True),
        sa.Column("unit", sa.String(100), nullable=True),
        sa.Column("is_hidden", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default="true"),
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
    op.create_index("ix_boq_items_tenant_id", "boq_items", ["tenant_id"])
    op.create_index(
        "ix_boq_items_tenant_project", "boq_items", ["tenant_id", "project_id"]
    )
    op.create_index(
        "ix_boq_items_tenant_document", "boq_items", ["tenant_id", "document_id"]
    )

    # RLS for boq_items
    op.execute("ALTER TABLE boq_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE boq_items FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON boq_items
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY app_bypass_policy ON boq_items
            USING (current_setting('app.tenant_id', true) IS NULL)
        """
    )


def downgrade() -> None:
    # boq_items
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON boq_items")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON boq_items")
    op.execute("ALTER TABLE boq_items DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_boq_items_tenant_document")
    op.drop_index("ix_boq_items_tenant_project")
    op.drop_index("ix_boq_items_tenant_id")
    op.drop_table("boq_items")

    # documents
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON documents")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON documents")
    op.execute("ALTER TABLE documents DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_documents_tenant_project")
    op.drop_index("ix_documents_tenant_id")
    op.drop_table("documents")
