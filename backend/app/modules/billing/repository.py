from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.models import (
    PaymentHistory,
    PaymentToken,
    ProjectCredit,
    Subscription,
)


class BillingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Subscriptions ────────────────────────────────────────────────

    async def get_active_subscription(self, tenant_id: uuid.UUID) -> Subscription | None:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Subscription)
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "active",
                Subscription.expires_at > now,
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_latest_subscription(self, tenant_id: uuid.UUID) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create_subscription(
        self,
        tenant_id: uuid.UUID,
        amount_paid: int,
        projects_limit: int,
        starts_at: datetime,
        expires_at: datetime,
        moyasar_payment_id: str | None = None,
        auto_renew: bool = False,
    ) -> Subscription:
        sub = Subscription(
            tenant_id=tenant_id,
            amount_paid=amount_paid,
            projects_limit=projects_limit,
            projects_used=0,
            status="active",
            auto_renew=auto_renew,
            starts_at=starts_at,
            expires_at=expires_at,
            moyasar_payment_id=moyasar_payment_id,
        )
        self.db.add(sub)
        await self.db.flush()
        return sub

    async def increment_projects_used(self, subscription_id: uuid.UUID) -> None:
        """Atomically increment projects_used with row lock."""
        await self.db.execute(
            text(
                "UPDATE subscriptions SET projects_used = projects_used + 1, "
                "updated_at = now() WHERE id = :sid"
            ),
            {"sid": subscription_id},
        )

    async def expire_subscription(self, subscription_id: uuid.UUID) -> None:
        await self.db.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(status="expired", updated_at=datetime.now(timezone.utc))
        )

    async def toggle_auto_renew(self, subscription_id: uuid.UUID, enabled: bool) -> None:
        await self.db.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(auto_renew=enabled, updated_at=datetime.now(timezone.utc))
        )

    async def cancel_all_for_tenant(self, tenant_id: uuid.UUID) -> None:
        """Turn off auto_renew and reset retry state on ALL subscriptions for a tenant."""
        await self.db.execute(
            update(Subscription)
            .where(Subscription.tenant_id == tenant_id)
            .values(
                auto_renew=False,
                renewal_attempts=0,
                next_retry_at=None,
                renewal_failed_at=None,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def expire_all_old_for_tenant(self, tenant_id: uuid.UUID, exclude_id: uuid.UUID) -> None:
        """Expire ALL active subscriptions for a tenant except the given one."""
        await self.db.execute(
            update(Subscription)
            .where(
                Subscription.tenant_id == tenant_id,
                Subscription.id != exclude_id,
                Subscription.status == "active",
            )
            .values(
                status="expired",
                auto_renew=False,
                renewal_attempts=0,
                next_retry_at=None,
                renewal_failed_at=None,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def get_expired_auto_renew_subscriptions(self) -> list[Subscription]:
        """Find subscriptions eligible for auto-renewal with retry logic."""
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(Subscription).where(
                Subscription.status == "active",
                Subscription.expires_at <= now,
                Subscription.auto_renew.is_(True),
                Subscription.renewal_attempts < 4,
                # Either never tried, or next_retry_at has passed
                (Subscription.next_retry_at.is_(None)) | (Subscription.next_retry_at <= now),
            )
        )
        return list(result.scalars().all())

    async def update_retry_state(
        self,
        subscription_id: uuid.UUID,
        renewal_attempts: int,
        next_retry_at: datetime | None,
        renewal_failed_at: datetime | None,
    ) -> None:
        await self.db.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(
                renewal_attempts=renewal_attempts,
                next_retry_at=next_retry_at,
                renewal_failed_at=renewal_failed_at,
                updated_at=datetime.now(timezone.utc),
            )
        )

    async def reset_retry_state(self, subscription_id: uuid.UUID) -> None:
        """Reset retry state — called after manual renewal or Guard 1 skip."""
        await self.db.execute(
            update(Subscription)
            .where(Subscription.id == subscription_id)
            .values(
                renewal_attempts=0,
                next_retry_at=None,
                renewal_failed_at=None,
                updated_at=datetime.now(timezone.utc),
            )
        )

    # ── Project Credits ──────────────────────────────────────────────

    async def get_credits(self, tenant_id: uuid.UUID) -> ProjectCredit | None:
        result = await self.db.execute(
            select(ProjectCredit).where(ProjectCredit.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_credits(self, tenant_id: uuid.UUID) -> ProjectCredit:
        credit = await self.get_credits(tenant_id)
        if not credit:
            credit = ProjectCredit(tenant_id=tenant_id, balance=0)
            self.db.add(credit)
            await self.db.flush()
        return credit

    async def increment_credits(self, tenant_id: uuid.UUID, amount: int = 1) -> None:
        """Upsert: increment balance or create with amount."""
        credit = await self.get_or_create_credits(tenant_id)
        await self.db.execute(
            text(
                "UPDATE project_credits SET balance = balance + :amt, "
                "updated_at = now() WHERE tenant_id = :tid"
            ),
            {"amt": amount, "tid": tenant_id},
        )

    async def decrement_credits(self, tenant_id: uuid.UUID) -> None:
        """Atomically decrement balance with row lock."""
        await self.db.execute(
            text(
                "UPDATE project_credits SET balance = balance - 1, "
                "updated_at = now() WHERE tenant_id = :tid AND balance > 0"
            ),
            {"tid": tenant_id},
        )

    # ── Payment History ──────────────────────────────────────────────

    async def create_payment_history(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        plan: str,
        amount: int,
        currency: str,
        given_id: uuid.UUID,
        payment_type: str = "manual",
        metadata_json: dict | None = None,
    ) -> PaymentHistory:
        ph = PaymentHistory(
            tenant_id=tenant_id,
            user_id=user_id,
            plan=plan,
            amount=amount,
            currency=currency,
            status="pending",
            given_id=given_id,
            payment_type=payment_type,
            metadata_json=metadata_json,
        )
        self.db.add(ph)
        await self.db.flush()
        return ph

    async def get_payment_by_id(self, payment_id: uuid.UUID) -> PaymentHistory | None:
        result = await self.db.execute(
            select(PaymentHistory).where(PaymentHistory.id == payment_id)
        )
        return result.scalar_one_or_none()

    async def get_payment_by_moyasar_id(self, moyasar_id: str) -> PaymentHistory | None:
        result = await self.db.execute(
            select(PaymentHistory).where(PaymentHistory.moyasar_payment_id == moyasar_id)
        )
        return result.scalar_one_or_none()

    async def update_payment_status(
        self,
        payment_id: uuid.UUID,
        status: str,
        moyasar_payment_id: str | None = None,
        paid_at: datetime | None = None,
    ) -> None:
        values: dict = {
            "status": status,
            "updated_at": datetime.now(timezone.utc),
        }
        if moyasar_payment_id:
            values["moyasar_payment_id"] = moyasar_payment_id
        if paid_at:
            values["paid_at"] = paid_at
        await self.db.execute(
            update(PaymentHistory)
            .where(PaymentHistory.id == payment_id)
            .values(**values)
        )

    async def list_payment_history(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        status_filter: str | None = None,
        plan_filter: str | None = None,
    ) -> tuple[list[PaymentHistory], int]:
        query = select(PaymentHistory).where(PaymentHistory.tenant_id == tenant_id)
        count_query = select(func.count(PaymentHistory.id)).where(
            PaymentHistory.tenant_id == tenant_id
        )

        if status_filter:
            query = query.where(PaymentHistory.status == status_filter)
            count_query = count_query.where(PaymentHistory.status == status_filter)
        else:
            # Exclude pending by default — only show paid and failed
            query = query.where(PaymentHistory.status != "pending")
            count_query = count_query.where(PaymentHistory.status != "pending")
        if plan_filter:
            query = query.where(PaymentHistory.plan == plan_filter)
            count_query = count_query.where(PaymentHistory.plan == plan_filter)

        total = (await self.db.execute(count_query)).scalar() or 0
        query = query.order_by(PaymentHistory.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    # ── Payment Tokens ───────────────────────────────────────────────

    async def get_active_token(self, tenant_id: uuid.UUID) -> PaymentToken | None:
        result = await self.db.execute(
            select(PaymentToken)
            .where(
                PaymentToken.tenant_id == tenant_id,
                PaymentToken.status == "active",
            )
            .order_by(PaymentToken.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_tokens(self, tenant_id: uuid.UUID) -> list[PaymentToken]:
        result = await self.db.execute(
            select(PaymentToken)
            .where(
                PaymentToken.tenant_id == tenant_id,
                PaymentToken.status == "active",
            )
            .order_by(PaymentToken.created_at.desc())
        )
        return list(result.scalars().all())

    async def save_token(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        moyasar_token: str,
        card_brand: str | None = None,
        last_four: str | None = None,
        expires_month: int | None = None,
        expires_year: int | None = None,
    ) -> PaymentToken:
        token = PaymentToken(
            tenant_id=tenant_id,
            user_id=user_id,
            moyasar_token=moyasar_token,
            card_brand=card_brand,
            last_four=last_four,
            expires_month=expires_month,
            expires_year=expires_year,
            status="active",
        )
        self.db.add(token)
        await self.db.flush()
        return token

    async def revoke_token(self, token_id: uuid.UUID) -> None:
        await self.db.execute(
            update(PaymentToken)
            .where(PaymentToken.id == token_id)
            .values(status="revoked", updated_at=datetime.now(timezone.utc))
        )

    async def get_token_by_id(self, token_id: uuid.UUID) -> PaymentToken | None:
        result = await self.db.execute(
            select(PaymentToken).where(PaymentToken.id == token_id)
        )
        return result.scalar_one_or_none()
