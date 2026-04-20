from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.moyasar_client import MoyasarClient
from app.modules.billing.repository import BillingRepository
from app.modules.billing.schemas import (
    BillingAlertItem,
    InitiatePaymentResponse,
    QuotaResponse,
    SubscriptionResponse,
)
from app.shared.quota import get_quota_status

logger = logging.getLogger(__name__)

PLAN_CONFIG = {
    "monthly": {"amount": 25000, "currency": "USD", "description": "Monthly Subscription - 25 Projects"},
    "per_project": {"amount": 2500, "currency": "USD", "description": "Per-Project Purchase - 1 Project"},
}


class BillingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = BillingRepository(db)
        self.moyasar = MoyasarClient()

    # ── Payment Initiation ───────────────────────────────────────────

    async def initiate_payment(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, plan: str
    ) -> InitiatePaymentResponse:
        if plan not in PLAN_CONFIG:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid plan: {plan}. Must be 'monthly' or 'per_project'.",
            )

        # For monthly: no active (non-expired) subscription allowed
        if plan == "monthly":
            active_sub = await self.repo.get_active_subscription(tenant_id)
            if active_sub:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An active subscription already exists. Wait until it expires or purchase per-project credits.",
                )

        cfg = PLAN_CONFIG[plan]
        given_id = uuid.uuid4()

        payment = await self.repo.create_payment_history(
            tenant_id=tenant_id,
            user_id=user_id,
            plan=plan,
            amount=cfg["amount"],
            currency=cfg["currency"],
            given_id=given_id,
        )

        return InitiatePaymentResponse(
            internal_id=str(payment.id),
            amount=cfg["amount"],
            currency=cfg["currency"],
            given_id=str(given_id),
            description=cfg["description"],
        )

    # ── Payment Verification ─────────────────────────────────────────

    async def verify_payment(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID, moyasar_payment_id: str
    ) -> dict:
        # Fetch payment from Moyasar
        try:
            moyasar_data = await self.moyasar.fetch_payment(moyasar_payment_id)
        except Exception as exc:
            logger.error("Moyasar fetch failed for %s: %s", moyasar_payment_id, exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to verify payment with payment provider.",
            )

        # Find internal record via metadata
        metadata = moyasar_data.get("metadata") or {}
        internal_id = metadata.get("internal_id")
        if not internal_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment metadata missing internal_id.",
            )

        payment = await self.repo.get_payment_by_id(uuid.UUID(internal_id))
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment record not found.",
            )

        # Idempotent — already processed
        if payment.status == "paid":
            quota = await get_quota_status(tenant_id, self.db)
            return self._build_verify_result(True, "Payment already processed.", tenant_id, quota)

        # Verify status, amount, currency
        if moyasar_data.get("status") != "paid":
            await self.repo.update_payment_status(
                payment.id, "failed", moyasar_payment_id=moyasar_payment_id
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Payment not successful. Status: {moyasar_data.get('status')}",
            )

        if moyasar_data.get("amount") != payment.amount:
            await self.repo.update_payment_status(
                payment.id, "failed", moyasar_payment_id=moyasar_payment_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount mismatch.",
            )

        if moyasar_data.get("currency", "").upper() != payment.currency:
            await self.repo.update_payment_status(
                payment.id, "failed", moyasar_payment_id=moyasar_payment_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Currency mismatch.",
            )

        # Mark paid
        now = datetime.now(timezone.utc)
        await self.repo.update_payment_status(
            payment.id, "paid", moyasar_payment_id=moyasar_payment_id, paid_at=now
        )

        # Activate subscription or increment credits
        await self._activate_plan(tenant_id, payment.plan, moyasar_payment_id)

        # Save card token if present
        source = moyasar_data.get("source") or {}
        token = source.get("token")
        if token:
            await self._save_card_token(
                tenant_id, user_id, token, source
            )

        quota = await get_quota_status(tenant_id, self.db)
        return self._build_verify_result(True, "Payment verified successfully.", tenant_id, quota)

    async def _activate_plan(
        self, tenant_id: uuid.UUID, plan: str, moyasar_payment_id: str | None
    ) -> None:
        now = datetime.now(timezone.utc)
        if plan == "monthly":
            await self.repo.create_subscription(
                tenant_id=tenant_id,
                amount_paid=PLAN_CONFIG["monthly"]["amount"],
                projects_limit=25,
                starts_at=now,
                expires_at=now + timedelta(days=30),
                moyasar_payment_id=moyasar_payment_id,
            )
        elif plan == "per_project":
            await self.repo.increment_credits(tenant_id, 1)

    async def _save_card_token(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        token: str,
        source: dict,
    ) -> None:
        # Extract card details from source
        card_brand = source.get("company") or source.get("type")
        last_four = source.get("number", "")[-4:] if source.get("number") else None
        month = source.get("month")
        year = source.get("year")

        await self.repo.save_token(
            tenant_id=tenant_id,
            user_id=user_id,
            moyasar_token=token,
            card_brand=card_brand,
            last_four=last_four,
            expires_month=int(month) if month else None,
            expires_year=int(year) if year else None,
        )

    def _build_verify_result(
        self, success: bool, message: str, tenant_id: uuid.UUID, quota
    ) -> dict:
        sub_resp = None
        if quota.subscription_projects_limit is not None:
            sub_resp = {
                "status": "active" if quota.source == "subscription" else "expired",
                "projects_used": quota.subscription_projects_used,
                "projects_limit": quota.subscription_projects_limit,
                "expires_at": quota.subscription_expires_at.isoformat() if quota.subscription_expires_at else None,
            }

        return {
            "success": success,
            "message": message,
            "quota": {
                "can_create": quota.can_create,
                "source": quota.source,
                "message": quota.message,
                "subscription": sub_resp,
                "credits_balance": quota.credits_balance,
            },
        }

    # ── Subscription Management ──────────────────────────────────────

    async def get_subscription(self, tenant_id: uuid.UUID) -> dict | None:
        sub = await self.repo.get_active_subscription(tenant_id)
        if not sub:
            sub = await self.repo.get_latest_subscription(tenant_id)
        if not sub:
            return None
        return {
            "id": str(sub.id),
            "status": sub.status,
            "projects_used": sub.projects_used,
            "projects_limit": sub.projects_limit,
            "starts_at": sub.starts_at.isoformat(),
            "expires_at": sub.expires_at.isoformat(),
            "auto_renew": sub.auto_renew,
            "amount_paid": sub.amount_paid,
        }

    async def toggle_auto_renew(self, tenant_id: uuid.UUID, enabled: bool) -> None:
        sub = await self.repo.get_active_subscription(tenant_id)
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No active subscription to toggle auto-renewal.",
            )
        await self.repo.toggle_auto_renew(sub.id, enabled)

    # ── Saved Cards ──────────────────────────────────────────────────

    async def list_cards(self, tenant_id: uuid.UUID) -> list[dict]:
        tokens = await self.repo.list_tokens(tenant_id)
        return [
            {
                "id": str(t.id),
                "card_brand": t.card_brand,
                "last_four": t.last_four,
                "expires_month": t.expires_month,
                "expires_year": t.expires_year,
                "created_at": t.created_at.isoformat(),
            }
            for t in tokens
        ]

    async def revoke_card(self, tenant_id: uuid.UUID, token_id: uuid.UUID) -> None:
        token = await self.repo.get_token_by_id(token_id)
        if not token or token.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Card not found.",
            )
        # Delete on Moyasar side (best effort)
        try:
            await self.moyasar.delete_token(token.moyasar_token)
        except Exception:
            logger.warning("Failed to delete token on Moyasar: %s", token.moyasar_token)
        await self.repo.revoke_token(token_id)

    # ── Payment History ──────────────────────────────────────────────

    async def list_payments(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        status_filter: str | None = None,
        plan_filter: str | None = None,
    ) -> dict:
        payments, total = await self.repo.list_payment_history(
            tenant_id, page=page, limit=limit,
            status_filter=status_filter, plan_filter=plan_filter,
        )
        return {
            "data": [
                {
                    "id": str(p.id),
                    "plan": p.plan,
                    "amount": p.amount,
                    "currency": p.currency,
                    "status": p.status,
                    "payment_type": p.payment_type,
                    "moyasar_payment_id": p.moyasar_payment_id,
                    "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                    "created_at": p.created_at.isoformat(),
                }
                for p in payments
            ],
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": (total + limit - 1) // limit if limit else 0,
            },
        }

    # ── Billing Alerts ───────────────────────────────────────────────

    async def get_alerts(self, tenant_id: uuid.UUID) -> list[dict]:
        alerts: list[dict] = []
        latest = await self.repo.get_latest_subscription(tenant_id)
        if not latest:
            return alerts

        now = datetime.now(timezone.utc)
        if latest.status == "expired" or (latest.status == "active" and latest.expires_at <= now):
            if latest.auto_renew:
                alerts.append({
                    "type": "renewal_failed",
                    "message": (
                        "Your subscription has expired and auto-renewal failed. "
                        "Please update your payment method to continue creating projects."
                    ),
                })
            else:
                alerts.append({
                    "type": "subscription_expired",
                    "message": (
                        "Your monthly subscription has expired. "
                        "Please renew your subscription or purchase individual projects to continue."
                    ),
                })
        return alerts
