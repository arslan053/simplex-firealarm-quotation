"""Add analysis_answers table with RLS

Revision ID: 006
Revises: 005
Create Date: 2026-03-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analysis_answers",
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
            "question_id",
            UUID(as_uuid=True),
            sa.ForeignKey("prompt_questions.id"),
            nullable=False,
        ),
        sa.Column("answer", sa.String(10), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("supporting_notes", sa.Text(), nullable=False),
        sa.Column("inferred_from", sa.String(10), nullable=False),
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
    op.create_index("ix_analysis_answers_tenant_id", "analysis_answers", ["tenant_id"])
    op.create_index(
        "ix_analysis_answers_tenant_project",
        "analysis_answers",
        ["tenant_id", "project_id"],
    )

    # RLS
    op.execute("ALTER TABLE analysis_answers ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE analysis_answers FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation_policy ON analysis_answers
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )
    op.execute(
        """
        CREATE POLICY app_bypass_policy ON analysis_answers
            USING (current_setting('app.tenant_id', true) IS NULL)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS app_bypass_policy ON analysis_answers")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_policy ON analysis_answers")
    op.execute("ALTER TABLE analysis_answers DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_analysis_answers_tenant_project")
    op.drop_index("ix_analysis_answers_tenant_id")
    op.drop_table("analysis_answers")
