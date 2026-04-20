from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.billing.schemas import (
    BillingAlertResponse,
    InitiatePaymentRequest,
    InitiatePaymentResponse,
    VerifyPaymentRequest,
)
from app.modules.billing.service import BillingService
from app.shared.quota import get_quota_status

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ── Quota (all authenticated users) ─────────────────────────────────

@router.get(
    "/quota",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
    ],
)
async def get_quota(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    quota = await get_quota_status(tenant_id, db)

    svc = BillingService(db)
    sub_data = await svc.get_subscription(tenant_id)

    return {
        "can_create": quota.can_create,
        "source": quota.source,
        "message": quota.message,
        "subscription": sub_data,
        "credits_balance": quota.credits_balance,
    }


# ── Payment Initiation (admin only) ─────────────────────────────────

@router.post(
    "/payments/initiate",
    response_model=InitiatePaymentResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def initiate_payment(
    body: InitiatePaymentRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    return await svc.initiate_payment(tenant_id, uuid.UUID(user.id), body.plan, body.quantity)


# ── Payment Verification (admin only) ───────────────────────────────

@router.post(
    "/payments/verify",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def verify_payment(
    body: VerifyPaymentRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    return await svc.verify_payment(tenant_id, uuid.UUID(user.id), body.moyasar_payment_id)


# ── Payment History (admin only) ─────────────────────────────────────

@router.get(
    "/payments",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def list_payments(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: str | None = Query(None),
    plan: str | None = Query(None),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    return await svc.list_payments(
        tenant_id, page=page, limit=limit,
        status_filter=status, plan_filter=plan,
    )


# ── Subscription (admin only) ────────────────────────────────────────

@router.get(
    "/subscription",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def get_subscription(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    return await svc.get_subscription(tenant_id)


# ── Saved Cards (admin only) ────────────────────────────────────────

@router.post(
    "/cards/update",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def update_card(
    body: VerifyPaymentRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    return await svc.update_card(tenant_id, uuid.UUID(user.id), body.moyasar_payment_id)


@router.get(
    "/cards",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def list_cards(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    return await svc.list_cards(tenant_id)



# ── Billing Alerts (admin only) ─────────────────────────────────────

@router.get(
    "/alerts",
    response_model=BillingAlertResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def get_alerts(
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant_id = uuid.UUID(request.state.tenant["id"])
    svc = BillingService(db)
    alerts = await svc.get_alerts(tenant_id)
    return {"alerts": alerts}


# ── Manual Renewal Trigger (super_admin only) ────────────────────────

@router.post(
    "/admin/run-renewal",
    dependencies=[
        require_role("super_admin"),
    ],
)
async def run_renewal_manually():
    from app.modules.billing.renewal_service import process_renewals
    count = await process_renewals()
    return {"message": f"Processed {count} renewal(s)."}
