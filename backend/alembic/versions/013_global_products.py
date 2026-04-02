"""Add products table with product_category_enum

Revision ID: 013
Revises: 012
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE product_category_enum AS ENUM (
            'MX Devices',
            'Idnet Devices',
            'IDNAC',
            'Audio Panel',
            'Special Items',
            'conventional',
            'PC-TSW',
            'mimic panel',
            'Panel',
            'Remote Annunciator',
            'Repeator'
        )
    """)
    op.execute("""
        CREATE TABLE products (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code        TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL,
            price       NUMERIC,
            currency    TEXT NOT NULL DEFAULT 'USD',
            category    product_category_enum NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS products")
    op.execute("DROP TYPE IF EXISTS product_category_enum")
