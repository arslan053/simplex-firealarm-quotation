"""Create billing tables (subscriptions, project_credits, payment_history, payment_tokens)

Revision ID: 039
Revises: 038
Create Date: 2026-04-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = "039"
down_revision: Union[str, None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── subscriptions ────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE subscriptions (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            amount_paid         INTEGER NOT NULL,
            projects_limit      INTEGER NOT NULL,
            projects_used       INTEGER NOT NULL DEFAULT 0,
            status              VARCHAR(20) NOT NULL DEFAULT 'active',
            auto_renew          BOOLEAN NOT NULL DEFAULT false,
            starts_at           TIMESTAMPTZ NOT NULL,
            expires_at          TIMESTAMPTZ NOT NULL,
            moyasar_payment_id  VARCHAR(100),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_subscriptions_tenant ON subscriptions (tenant_id)")
    op.execute(
        "CREATE INDEX ix_subscriptions_tenant_status ON subscriptions (tenant_id, status)"
    )
    op.execute("ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE subscriptions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON subscriptions
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON subscriptions
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)

    # ── project_credits ──────────────────────────────────────────────
    op.execute("""
        CREATE TABLE project_credits (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   UUID NOT NULL REFERENCES tenants(id) UNIQUE,
            balance     INTEGER NOT NULL DEFAULT 0,
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("ALTER TABLE project_credits ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE project_credits FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON project_credits
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON project_credits
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)

    # ── payment_history ──────────────────────────────────────────────
    op.execute("""
        CREATE TABLE payment_history (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           UUID NOT NULL REFERENCES tenants(id),
            user_id             UUID NOT NULL REFERENCES users(id),
            plan                VARCHAR(20) NOT NULL,
            amount              INTEGER NOT NULL,
            currency            VARCHAR(3) NOT NULL DEFAULT 'USD',
            status              VARCHAR(20) NOT NULL DEFAULT 'pending',
            moyasar_payment_id  VARCHAR(100),
            given_id            UUID NOT NULL,
            payment_type        VARCHAR(20) NOT NULL DEFAULT 'manual',
            metadata_json       JSONB,
            paid_at             TIMESTAMPTZ,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_payment_history_tenant ON payment_history (tenant_id)")
    op.execute("CREATE INDEX ix_payment_history_given_id ON payment_history (given_id)")
    op.execute(
        "CREATE INDEX ix_payment_history_moyasar ON payment_history (moyasar_payment_id)"
    )
    op.execute("ALTER TABLE payment_history ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payment_history FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON payment_history
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON payment_history
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)

    # ── payment_tokens ───────────────────────────────────────────────
    op.execute("""
        CREATE TABLE payment_tokens (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id       UUID NOT NULL REFERENCES tenants(id),
            user_id         UUID NOT NULL REFERENCES users(id),
            moyasar_token   VARCHAR(100) NOT NULL,
            card_brand      VARCHAR(20),
            last_four       VARCHAR(4),
            expires_month   INTEGER,
            expires_year    INTEGER,
            status          VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_payment_tokens_tenant ON payment_tokens (tenant_id)")
    op.execute("ALTER TABLE payment_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE payment_tokens FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation_policy ON payment_tokens
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
    """)
    op.execute("""
        CREATE POLICY app_bypass_policy ON payment_tokens
            USING (current_setting('app.tenant_id', true) IS NULL)
    """)


def downgrade() -> None:
    for table in ("payment_tokens", "payment_history", "project_credits", "subscriptions"):
        op.execute(f"DROP POLICY IF EXISTS app_bypass_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_policy ON {table}")
        op.execute(f"DROP TABLE IF EXISTS {table}")
