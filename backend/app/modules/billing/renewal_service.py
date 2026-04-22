from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.config import settings
from app.database import async_session_factory
from app.modules.billing.moyasar_client import MoyasarClient
from app.modules.billing.repository import BillingRepository

logger = logging.getLogger(__name__)

MONTHLY_AMOUNT = 25000
MONTHLY_PROJECTS_LIMIT = 25

# Retry schedule: offsets from renewal_failed_at
RETRY_OFFSETS = [
    timedelta(hours=0),   # Attempt 1: immediately
    timedelta(hours=6),   # Attempt 2: 6h after first failure
    timedelta(hours=24),  # Attempt 3: 24h after first failure
    timedelta(hours=72),  # Attempt 4: 72h after first failure
]


def _compute_next_retry(renewal_failed_at: datetime, attempts: int) -> datetime | None:
    if attempts >= len(RETRY_OFFSETS):
        return None
    return renewal_failed_at + RETRY_OFFSETS[attempts]


# ━━━ Shared core: charge saved card and activate subscription ━━━━━━━

@dataclass
class ChargeResult:
    success: bool
    message: str
    moyasar_payment_id: str | None = None
    decline_reason: str | None = None


async def charge_saved_card(
    repo: BillingRepository,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    payment_type: str = "manual",
) -> ChargeResult:
    """
    Charge the tenant's saved card for a monthly subscription.
    Shared by both cron auto-renewal and manual "Renew Now".
    Returns ChargeResult — caller decides how to handle success/failure.
    """
    now = datetime.now(timezone.utc)

    # Guard 1: active subscription already exists
    active = await repo.get_active_subscription(tenant_id)
    if active:
        return ChargeResult(success=True, message="Subscription already active.")

    # Must have a saved card
    token = await repo.get_active_token(tenant_id)
    if not token:
        return ChargeResult(success=False, message="No saved payment method.")

    # Create pending payment record
    given_id = uuid.uuid4()
    payment = await repo.create_payment_history(
        tenant_id=tenant_id,
        user_id=user_id,
        plan="monthly",
        amount=MONTHLY_AMOUNT,
        currency="SAR",
        given_id=given_id,
        payment_type=payment_type,
    )

    # Charge via Moyasar
    moyasar = MoyasarClient()
    callback_url = f"{settings.FRONTEND_URL}/billing/verify"

    try:
        result = await moyasar.charge_token(
            token=token.moyasar_token,
            amount=MONTHLY_AMOUNT,
            currency="SAR",
            description="Monthly Subscription Renewal",
            callback_url=callback_url,
            metadata={
                "internal_id": str(payment.id),
                "tenant_id": str(tenant_id),
                "plan": "monthly",
                "type": payment_type,
            },
        )
    except Exception as exc:
        logger.error("Moyasar charge failed for tenant %s: %s", tenant_id, exc)
        await repo.update_payment_status(payment.id, "failed")
        return ChargeResult(success=False, message=str(exc), decline_reason=str(exc))

    moyasar_payment_id = result.get("id")

    if result.get("status") == "paid":
        # Guard 2: double-check no active sub appeared during charge
        active_again = await repo.get_active_subscription(tenant_id)
        if active_again:
            logger.warning("Guard 2: refunding %s — active sub appeared for tenant %s", moyasar_payment_id, tenant_id)
            try:
                await moyasar.refund_payment(moyasar_payment_id)
            except Exception:
                logger.exception("Guard 2 refund failed for %s", moyasar_payment_id)
            await repo.update_payment_status(payment.id, "failed", moyasar_payment_id=moyasar_payment_id)
            return ChargeResult(success=True, message="Subscription already active — charge refunded.")

        await repo.update_payment_status(payment.id, "paid", moyasar_payment_id=moyasar_payment_id, paid_at=now)

        # Expire old sub, create new one
        new_sub = await repo.create_subscription(
            tenant_id=tenant_id,
            amount_paid=MONTHLY_AMOUNT,
            projects_limit=MONTHLY_PROJECTS_LIMIT,
            starts_at=now,
            expires_at=now + timedelta(days=30),
            moyasar_payment_id=moyasar_payment_id,
            auto_renew=True,
        )
        # Expire ALL old subscriptions — prevents old subs from triggering cron again
        await repo.expire_all_old_for_tenant(tenant_id, new_sub.id)
        logger.info("Subscription renewed for tenant %s (type=%s)", tenant_id, payment_type)
        return ChargeResult(success=True, message="Subscription renewed successfully!", moyasar_payment_id=moyasar_payment_id)
    else:
        # Payment declined
        source = result.get("source") or {}
        decline_reason = source.get("message") or result.get("message") or "unknown"
        response_code = source.get("response_code") or ""

        await repo.update_payment_status(payment.id, "failed", moyasar_payment_id=moyasar_payment_id)
        await _store_decline_reason(repo, payment.id, decline_reason, response_code)

        logger.warning("Renewal failed for tenant %s: reason=%s", tenant_id, decline_reason)
        return ChargeResult(success=False, message=decline_reason, moyasar_payment_id=moyasar_payment_id, decline_reason=decline_reason)


# ━━━ Cron: process all expired subscriptions ━━━━━━━━━━━━━━━━━━━━━━━

async def process_renewals() -> int:
    """
    Find expired subscriptions with auto_renew and attempt to charge.
    Implements retry schedule. Returns the number processed.
    """
    async with async_session_factory() as db:
        try:
            repo = BillingRepository(db)
            expired_subs = await repo.get_expired_auto_renew_subscriptions()

            if not expired_subs:
                return 0

            logger.info("Found %d expired subscriptions to process", len(expired_subs))
            count = 0

            for sub in expired_subs:
                try:
                    token = await repo.get_active_token(sub.tenant_id)
                    user_id = token.user_id if token else sub.tenant_id

                    result = await charge_saved_card(repo, sub.tenant_id, user_id, payment_type="auto_renewal")

                    if not result.success and result.message != "Subscription already active.":
                        await _handle_retry_failure(repo, sub, datetime.now(timezone.utc))

                    count += 1
                except Exception:
                    logger.exception("Failed to process subscription %s", sub.id)

            await db.commit()
            return count

        except Exception:
            await db.rollback()
            logger.exception("Error in renewal process")
            return 0


async def _handle_retry_failure(repo: BillingRepository, sub, now: datetime) -> None:
    """Update retry state after a failed attempt."""
    failed_at = sub.renewal_failed_at or now
    attempts = sub.renewal_attempts + 1

    if attempts >= 4:
        await repo.expire_subscription(sub.id)
        await repo.update_retry_state(sub.id, renewal_attempts=attempts, next_retry_at=None, renewal_failed_at=failed_at)
        logger.info("All retry attempts exhausted for subscription %s — expired", sub.id)
    else:
        next_retry = _compute_next_retry(failed_at, attempts)
        await repo.update_retry_state(sub.id, renewal_attempts=attempts, next_retry_at=next_retry, renewal_failed_at=failed_at)
        logger.info("Retry %d/4 for subscription %s — next at %s", attempts, sub.id, next_retry)


async def _store_decline_reason(repo: BillingRepository, payment_id: uuid.UUID, reason: str, code: str) -> None:
    """Store Moyasar decline reason in payment_history.metadata_json."""
    from sqlalchemy import update as sa_update
    from app.modules.billing.models import PaymentHistory
    await repo.db.execute(
        sa_update(PaymentHistory)
        .where(PaymentHistory.id == payment_id)
        .values(metadata_json={"decline_reason": reason, "decline_code": code})
    )
