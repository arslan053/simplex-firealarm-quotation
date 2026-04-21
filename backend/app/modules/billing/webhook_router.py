from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import get_worker_db
from app.modules.billing.moyasar_client import MoyasarClient
from app.modules.billing.repository import BillingRepository

logger = logging.getLogger(__name__)

webhook_router = APIRouter(prefix="/api/billing/webhooks", tags=["billing-webhooks"])

PLAN_CONFIG = {
    "monthly": {"amount": 25000, "projects_limit": 25},
    "per_project": {"amount": 2500},
}


@webhook_router.post("/moyasar")
async def moyasar_webhook(request: Request):
    """
    Webhook endpoint called by Moyasar (server-to-server).
    No JWT auth — validated via secret_token.
    Returns 200 immediately, processes asynchronously.
    """
    body = await request.json()

    secret_token = body.get("secret_token")
    if not secret_token or secret_token != settings.MOYASAR_WEBHOOK_SECRET:
        return JSONResponse(status_code=401, content={"detail": "Invalid secret_token"})

    asyncio.create_task(_process_webhook(body))
    return JSONResponse(status_code=200, content={"status": "received"})


async def _process_webhook(body: dict) -> None:
    """Process webhook payload asynchronously."""
    try:
        data = body.get("data") or body
        payment_id = data.get("id")

        if not payment_id:
            logger.warning("Webhook missing payment id")
            return

        metadata = data.get("metadata") or {}
        internal_id = metadata.get("internal_id")
        tenant_id = metadata.get("tenant_id")

        if not internal_id or not tenant_id:
            logger.error(
                "Webhook missing metadata for moyasar payment %s: internal_id=%s, tenant_id=%s",
                payment_id, internal_id, tenant_id,
            )
            return

        async with get_worker_db(tenant_id) as db:
            repo = BillingRepository(db)

            payment = await repo.get_payment_by_id(uuid.UUID(internal_id))
            if not payment:
                logger.warning("Webhook: payment record not found: %s", internal_id)
                return

            # Idempotent: skip if already processed
            if payment.status == "paid":
                logger.info("Webhook: payment %s already processed, skipping", internal_id)
                return

            payment_status = data.get("status")
            now = datetime.now(timezone.utc)
            tid = uuid.UUID(tenant_id)

            if payment_status == "paid":
                # Verify amount
                if data.get("amount") != payment.amount:
                    logger.error(
                        "Webhook: amount mismatch for %s: expected %s, got %s",
                        internal_id, payment.amount, data.get("amount"),
                    )
                    await repo.update_payment_status(
                        payment.id, "failed", moyasar_payment_id=payment_id
                    )
                    return

                # ━━━ GUARD 3: Check active subscription BEFORE marking paid ━━━
                if payment.plan == "monthly":
                    active_sub = await repo.get_active_subscription(tid)
                    if active_sub:
                        logger.warning(
                            "Guard 3: active sub exists for tenant %s — skipping, refunding %s",
                            tenant_id, payment_id,
                        )
                        await repo.update_payment_status(
                            payment.id, "failed", moyasar_payment_id=payment_id
                        )
                        try:
                            moyasar = MoyasarClient()
                            await moyasar.refund_payment(payment_id)
                            logger.info("Guard 3: auto-refunded %s", payment_id)
                        except Exception:
                            logger.exception("Guard 3: refund failed for %s", payment_id)
                        return

                # Mark paid
                await repo.update_payment_status(
                    payment.id, "paid", moyasar_payment_id=payment_id, paid_at=now
                )

                # Activate plan
                if payment.plan == "monthly":
                    new_sub = await repo.create_subscription(
                        tenant_id=tid,
                        amount_paid=PLAN_CONFIG["monthly"]["amount"],
                        projects_limit=PLAN_CONFIG["monthly"]["projects_limit"],
                        starts_at=now,
                        expires_at=now + timedelta(days=30),
                        moyasar_payment_id=payment_id,
                        auto_renew=True,
                    )
                    await repo.expire_all_old_for_tenant(tid, new_sub.id)
                elif payment.plan == "per_project":
                    qty = (payment.metadata_json or {}).get("quantity", 1)
                    await repo.increment_credits(tid, qty)

                # Save card token only for monthly subscription payments
                source = data.get("source") or {}
                token = source.get("token")
                if token and payment.plan == "monthly":
                    card_brand = source.get("company") or source.get("type")
                    last_four = source.get("number", "")[-4:] if source.get("number") else None
                    await repo.save_token(
                        tenant_id=tid,
                        user_id=payment.user_id,
                        moyasar_token=token,
                        card_brand=card_brand,
                        last_four=last_four,
                        expires_month=int(source["month"]) if source.get("month") else None,
                        expires_year=int(source["year"]) if source.get("year") else None,
                    )

                logger.info("Webhook: payment %s activated successfully", internal_id)

            elif payment_status == "failed":
                # Store decline reason from Moyasar
                source = data.get("source") or {}
                decline_reason = source.get("message") or data.get("message") or ""
                decline_code = source.get("response_code") or ""

                await repo.update_payment_status(
                    payment.id, "failed", moyasar_payment_id=payment_id
                )

                # Store decline reason in metadata_json
                if decline_reason:
                    from sqlalchemy import update as sa_update
                    from app.modules.billing.models import PaymentHistory
                    await repo.db.execute(
                        sa_update(PaymentHistory)
                        .where(PaymentHistory.id == payment.id)
                        .values(metadata_json={"decline_reason": decline_reason, "decline_code": decline_code})
                    )

                logger.info(
                    "Webhook: payment %s failed — reason: %s, code: %s",
                    internal_id, decline_reason, decline_code,
                )

    except Exception:
        logger.exception("Error processing Moyasar webhook")
