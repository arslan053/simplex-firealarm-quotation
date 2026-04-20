from __future__ import annotations

import asyncio
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
RENEWAL_INTERVAL_SECONDS = 3600  # Check every hour


async def process_renewals() -> int:
    """
    Find expired subscriptions with auto_renew enabled and attempt to charge
    the tenant's saved card. Returns the number of renewals attempted.
    """
    # Use a plain session (no RLS context) — app_bypass_policy allows this
    async with async_session_factory() as db:
        try:
            repo = BillingRepository(db)
            expired_subs = await repo.get_expired_auto_renew_subscriptions()

            if not expired_subs:
                return 0

            logger.info("Found %d expired subscriptions to renew", len(expired_subs))
            count = 0

            for sub in expired_subs:
                try:
                    await _renew_subscription(db, repo, sub)
                    count += 1
                except Exception:
                    logger.exception(
                        "Failed to renew subscription %s for tenant %s",
                        sub.id, sub.tenant_id,
                    )

            await db.commit()
            return count

        except Exception:
            await db.rollback()
            logger.exception("Error in renewal process")
            return 0


async def _renew_subscription(db, repo: BillingRepository, sub) -> None:
    """Attempt to renew a single subscription."""
    tenant_id = sub.tenant_id
    now = datetime.now(timezone.utc)

    # Find active token
    token = await repo.get_active_token(tenant_id)
    if not token:
        logger.warning("No saved token for tenant %s — expiring subscription", tenant_id)
        await repo.expire_subscription(sub.id)
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
        await repo.update_payment_status(payment.id, "failed")
        await repo.expire_subscription(sub.id)
        return

    if result.get("status") == "paid":
        moyasar_payment_id = result.get("id")
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
        await repo.update_payment_status(
            payment.id, "failed",
            moyasar_payment_id=result.get("id"),
        )
        await repo.expire_subscription(sub.id)
        logger.warning(
            "Auto-renewal failed for tenant %s: status=%s",
            tenant_id, result.get("status"),
        )


async def renewal_loop() -> None:
    """Background loop that periodically checks for subscriptions to renew."""
    while True:
        try:
            count = await process_renewals()
            if count:
                logger.info("Renewal cycle completed: %d renewed", count)
        except Exception:
            logger.exception("Unhandled error in renewal loop")
        await asyncio.sleep(RENEWAL_INTERVAL_SECONDS)
