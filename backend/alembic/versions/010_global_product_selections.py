"""Add global_product_selections table with side and kind enums

Revision ID: 010
Revises: 009
Create Date: 2026-03-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE product_selection_side_enum AS ENUM ('MX', 'IDNet')")
    op.execute("CREATE TYPE product_selection_kind_enum AS ENUM ('single', 'combo')")
    op.execute("""
        CREATE TABLE global_product_selections (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            side        product_selection_side_enum NOT NULL,
            selection_kind product_selection_kind_enum NOT NULL,
            product_codes TEXT[] NOT NULL,
            descriptions  TEXT[] NOT NULL,
            codes_key   TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_gps_side_codes_key UNIQUE (side, codes_key)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS global_product_selections")
    op.execute("DROP TYPE IF EXISTS product_selection_kind_enum")
    op.execute("DROP TYPE IF EXISTS product_selection_side_enum")
