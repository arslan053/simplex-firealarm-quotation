from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


# ── Requests ─────────────────────────────────────────────────────────

class InitiatePaymentRequest(BaseModel):
    plan: str  # "monthly" | "per_project"


class VerifyPaymentRequest(BaseModel):
    moyasar_payment_id: str


class AutoRenewToggleRequest(BaseModel):
    enabled: bool


# ── Responses ────────────────────────────────────────────────────────

class InitiatePaymentResponse(BaseModel):
    internal_id: str
    amount: int
    currency: str
    given_id: str
    description: str


class SubscriptionResponse(BaseModel):
    id: str
    status: str
    projects_used: int
    projects_limit: int
    starts_at: datetime
    expires_at: datetime
    auto_renew: bool
    amount_paid: int

    class Config:
        from_attributes = True


class QuotaResponse(BaseModel):
    can_create: bool
    source: str | None
    message: str
    subscription: SubscriptionResponse | None
    credits_balance: int


class PaymentHistoryResponse(BaseModel):
    id: str
    plan: str
    amount: int
    currency: str
    status: str
    payment_type: str
    moyasar_payment_id: str | None
    paid_at: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentHistoryListResponse(BaseModel):
    data: list[PaymentHistoryResponse]
    pagination: PaginationMeta


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class SavedCardResponse(BaseModel):
    id: str
    card_brand: str | None
    last_four: str | None
    expires_month: int | None
    expires_year: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class BillingAlertItem(BaseModel):
    type: str
    message: str


class BillingAlertResponse(BaseModel):
    alerts: list[BillingAlertItem]


class VerifyPaymentResponse(BaseModel):
    success: bool
    message: str
    quota: QuotaResponse | None
