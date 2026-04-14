"""Create tenant_product_prices table and seed existing tenants

Revision ID: 036
Revises: 035
Create Date: 2026-04-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tenant_product_prices (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            price NUMERIC NOT NULL DEFAULT 0,
            currency TEXT NOT NULL DEFAULT 'USD',
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            UNIQUE (tenant_id, product_id)
        );
    """)

    op.execute(
        "CREATE INDEX ix_tpp_tenant ON tenant_product_prices(tenant_id);"
    )

    # RLS policies
    op.execute(
        "ALTER TABLE tenant_product_prices ENABLE ROW LEVEL SECURITY;"
    )
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON tenant_product_prices
            USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON tenant_product_prices
            USING (
                current_setting('app.current_tenant_id', true) IS NULL
                OR current_setting('app.current_tenant_id', true) = ''
            );
    """)

    # Seed prices for all existing tenants from global product prices
    op.execute("""
        INSERT INTO tenant_product_prices (tenant_id, product_id, price, currency)
        SELECT t.id, p.id, COALESCE(p.price, 0), p.currency
        FROM tenants t
        CROSS JOIN products p
        ON CONFLICT (tenant_id, product_id) DO NOTHING;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS tenant_product_prices;")
