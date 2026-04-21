from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.repository import BillingRepository


@dataclass
class QuotaStatus:
    can_create: bool
    source: str | None  # "subscription" | "credits" | None
    message: str
    subscription_projects_used: int | None
    subscription_projects_limit: int | None
    subscription_expires_at: datetime | None
    credits_balance: int


async def get_quota_status(tenant_id: uuid.UUID, db: AsyncSession) -> QuotaStatus:
    """Check if the tenant can create a project. Returns status with a user-facing message."""
    repo = BillingRepository(db)

    sub = await repo.get_active_subscription(tenant_id)
    credit = await repo.get_credits(tenant_id)
    balance = credit.balance if credit else 0

    # Check subscription first (time-limited — use it or lose it)
    if sub and sub.projects_used < sub.projects_limit:
        return QuotaStatus(
            can_create=True,
            source="subscription",
            message=f"{sub.projects_limit - sub.projects_used} projects remaining in your subscription.",
            subscription_projects_used=sub.projects_used,
            subscription_projects_limit=sub.projects_limit,
            subscription_expires_at=sub.expires_at,
            credits_balance=balance,
        )

    # Check per-project credits
    if balance > 0:
        return QuotaStatus(
            can_create=True,
            source="credits",
            message=f"{balance} project credit{'s' if balance != 1 else ''} remaining.",
            subscription_projects_used=sub.projects_used if sub else None,
            subscription_projects_limit=sub.projects_limit if sub else None,
            subscription_expires_at=sub.expires_at if sub else None,
            credits_balance=balance,
        )

    # No quota — determine the specific message
    latest_sub = await repo.get_latest_subscription(tenant_id)

    if sub and sub.projects_used >= sub.projects_limit:
        # Active subscription but all projects used
        message = (
            "You've used all 25 projects in your current subscription. "
            "You can purchase additional projects individually until your subscription renews."
        )
    elif latest_sub and latest_sub.status == "expired":
        # Had a subscription but it expired
        message = (
            "Your monthly subscription has expired. Please renew your subscription "
            "or purchase individual projects to continue."
        )
    elif latest_sub is None and balance == 0:
        # Never had anything
        message = (
            "You need an active subscription or purchased project credits to create projects. "
            "Visit Billing to get started."
        )
    else:
        # Per-project credits used up, no active sub
        message = (
            "Your purchased project credits have been used. Purchase more projects "
            "or subscribe to a monthly plan for better value."
        )

    return QuotaStatus(
        can_create=False,
        source=None,
        message=message,
        subscription_projects_used=sub.projects_used if sub else (latest_sub.projects_used if latest_sub else None),
        subscription_projects_limit=sub.projects_limit if sub else (latest_sub.projects_limit if latest_sub else None),
        subscription_expires_at=sub.expires_at if sub else (latest_sub.expires_at if latest_sub else None),
        credits_balance=balance,
    )


async def consume_quota(tenant_id: uuid.UUID, source: str, db: AsyncSession) -> None:
    """Atomically consume one project from the given source."""
    repo = BillingRepository(db)

    if source == "subscription":
        sub = await repo.get_active_subscription(tenant_id)
        if sub:
            await repo.increment_projects_used(sub.id)
    elif source == "credits":
        await repo.decrement_credits(tenant_id)
