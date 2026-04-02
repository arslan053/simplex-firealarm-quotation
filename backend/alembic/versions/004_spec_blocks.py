"""Add spec_blocks table with RLS

Revision ID: 004
Revises: 003
Create Date: 2024-01-04 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "spec_blocks",
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
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
            nullable=False,
        ),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column(
            "parent_id",
            UUID(as_uuid=True),
            sa.ForeignKey("spec_blocks.id"),
            nullable=True,
        ),
        sa.Column("order_in_page", sa.Integer(), nullable=False),
        sa.Column("style", sa.Text(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("list_kind", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
    )
    op.create_index("ix_spec_blocks_doc_page", "spec_blocks", ["document_id", "page_no"])
    op.create_index("ix_spec_blocks_parent", "spec_blocks", ["parent_id"])

    # RLS for spec_blocks
    op.execute("ALTER TABLE spec_blocks ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE spec_blocks FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON spec_blocks
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY app_bypass_policy ON spec_blocks
            USING (current_setting('app.tenant_id', true) IS NULL)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON spec_blocks")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON spec_blocks")
    op.execute("ALTER TABLE spec_blocks DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_spec_blocks_parent")
    op.drop_index("ix_spec_blocks_doc_page")
    op.drop_table("spec_blocks")
