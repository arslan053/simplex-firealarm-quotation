from __future__ import annotations

import logging
import uuid
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
    """Calculate next_retry_at based on retry schedule."""
    if attempts >= len(RETRY_OFFSETS):
        return None  # No more retries
    return renewal_failed_at + RETRY_OFFSETS[attempts]


async def process_renewals() -> int:
    """
    Find expired subscriptions with auto_renew and attempt to charge.
    Implements retry schedule and all 5 safety guards.
    Returns the number of renewals attempted.
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
                    await _renew_subscription(db, repo, sub)
                    count += 1
                except Exception:
                    logger.exception(
                        "Failed to process subscription %s for tenant %s",
                        sub.id, sub.tenant_id,
                    )

            await db.commit()
            return count

        except Exception:
            await db.rollback()
            logger.exception("Error in renewal process")
            return 0


async def _renew_subscription(db, repo: BillingRepository, sub) -> None:
    """Attempt to renew a single subscription with safety guards."""
    tenant_id = sub.tenant_id
    now = datetime.now(timezone.utc)

    # ━━━ GUARD 1: Check if tenant already has an active subscription ━━━
    active = await repo.get_active_subscription(tenant_id)
    if active:
        logger.info(
            "Guard 1: tenant %s already has active subscription %s — skipping, resetting retry",
            tenant_id, active.id,
        )
        await repo.reset_retry_state(sub.id)
        return

    # Find active token
    token = await repo.get_active_token(tenant_id)
    if not token:
        logger.warning("No saved token for tenant %s — expiring subscription", tenant_id)
        if sub.renewal_attempts >= 3:
            await repo.expire_subscription(sub.id)
        else:
            failed_at = sub.renewal_failed_at or now
            attempts = sub.renewal_attempts + 1
            await repo.update_retry_state(
                sub.id,
                renewal_attempts=attempts,
                next_retry_at=_compute_next_retry(failed_at, attempts),
                renewal_failed_at=failed_at,
            )
        return

    # Create pending payment record
    given_id = uuid.uuid4()
    payment = await repo.create_payment_history(
        tenant_id=tenant_id,
        user_id=token.user_id,
        plan="monthly",
        amount=MONTHLY_AMOUNT,
        currency="USD",
        given_id=given_id,
        payment_type="auto_renewal",
    )

    # Charge via Moyasar
    moyasar = MoyasarClient()
    callback_url = f"{settings.FRONTEND_URL}/billing/verify"

    try:
        result = await moyasar.charge_token(
            token=token.moyasar_token,
            amount=MONTHLY_AMOUNT,
            currency="USD",
            description="Monthly subscription auto-renewal",
            callback_url=callback_url,
            metadata={
                "internal_id": str(payment.id),
                "tenant_id": str(tenant_id),
                "plan": "monthly",
                "type": "auto_renewal",
            },
        )
    except Exception as exc:
        logger.error("Moyasar charge failed for tenant %s: %s", tenant_id, exc)
        decline_reason = str(exc)
        await repo.update_payment_status(payment.id, "failed")
        # Store decline reason
        await _store_decline_reason(repo, payment.id, decline_reason, "")
        await _handle_retry_failure(repo, sub, now)
        return

    moyasar_payment_id = result.get("id")

    if result.get("status") == "paid":
        # ━━━ GUARD 2: Double-check no active sub was created between check and now ━━━
        active_again = await repo.get_active_subscription(tenant_id)
        if active_again:
            logger.warning(
                "Guard 2: active subscription appeared for tenant %s after charge — refunding %s",
                tenant_id, moyasar_payment_id,
            )
            try:
                await moyasar.refund_payment(moyasar_payment_id)
            except Exception:
                logger.exception("Failed to auto-refund %s", moyasar_payment_id)
            await repo.update_payment_status(
                payment.id, "failed", moyasar_payment_id=moyasar_payment_id
            )
            await repo.reset_retry_state(sub.id)
            return

        await repo.update_payment_status(
            payment.id, "paid",
            moyasar_payment_id=moyasar_payment_id,
            paid_at=now,
        )
        # Expire old subscription
        await repo.expire_subscription(sub.id)
        # Create new subscription (carry forward auto_renew)
        await repo.create_subscription(
            tenant_id=tenant_id,
            amount_paid=MONTHLY_AMOUNT,
            projects_limit=MONTHLY_PROJECTS_LIMIT,
            starts_at=now,
            expires_at=now + timedelta(days=30),
            moyasar_payment_id=moyasar_payment_id,
            auto_renew=True,
        )
        logger.info("Auto-renewed subscription for tenant %s", tenant_id)
    else:
        # Payment failed
        source = result.get("source") or {}
        decline_reason = source.get("message") or result.get("message") or "unknown"
        response_code = source.get("response_code") or ""

        await repo.update_payment_status(
            payment.id, "failed", moyasar_payment_id=moyasar_payment_id
        )
        await _store_decline_reason(repo, payment.id, decline_reason, response_code)
        await _handle_retry_failure(repo, sub, now)

        logger.warning(
            "Auto-renewal failed for tenant %s: reason=%s, code=%s",
            tenant_id, decline_reason, response_code,
        )


async def _handle_retry_failure(repo: BillingRepository, sub, now: datetime) -> None:
    """Update retry state after a failed attempt."""
    failed_at = sub.renewal_failed_at or now
    attempts = sub.renewal_attempts + 1

    if attempts >= 4:
        # All retries exhausted — expire
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


