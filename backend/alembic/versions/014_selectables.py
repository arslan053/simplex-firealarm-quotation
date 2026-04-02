"""Add selectables and selectable_products tables with enums

Revision ID: 014
Revises: 013
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TYPE selectable_category_enum AS ENUM (
            'mx_detection_device',
            'idnet_detection_device',
            'addressable_notification_device',
            'non_addressable_notification_device'
        )
    """)
    op.execute("""
        CREATE TYPE selection_type_enum AS ENUM (
            'single',
            'combo'
        )
    """)
    op.execute("""
        CREATE TABLE selectables (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            category            selectable_category_enum NOT NULL,
            selection_type      selection_type_enum NOT NULL,
            boq_match_phrases   TEXT[] NOT NULL,
            description         TEXT,
            specification_hints TEXT,
            priority            TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE selectable_products (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            selectable_id   UUID NOT NULL REFERENCES selectables(id) ON DELETE CASCADE,
            product_id      UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_selectable_product UNIQUE (selectable_id, product_id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS selectable_products")
    op.execute("DROP TABLE IF EXISTS selectables")
    op.execute("DROP TYPE IF EXISTS selection_type_enum")
    op.execute("DROP TYPE IF EXISTS selectable_category_enum")
