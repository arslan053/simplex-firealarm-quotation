from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDPrimaryKey


class Subscription(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "subscriptions"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    amount_paid: Mapped[int] = mapped_column(Integer, nullable=False)
    projects_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    projects_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    moyasar_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    renewal_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    renewal_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_subscriptions_tenant", "tenant_id"),
        Index("ix_subscriptions_tenant_status", "tenant_id", "status"),
    )


class ProjectCredit(Base, UUIDPrimaryKey):
    __tablename__ = "project_credits"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, unique=True
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default="now()",
    )


class PaymentHistory(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "payment_history"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SAR")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    moyasar_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    given_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    payment_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_payment_history_tenant", "tenant_id"),
        Index("ix_payment_history_given_id", "given_id"),
        Index("ix_payment_history_moyasar", "moyasar_payment_id"),
    )


class PaymentToken(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "payment_tokens"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    moyasar_token: Mapped[str] = mapped_column(String(100), nullable=False)
    card_brand: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_four: Mapped[str | None] = mapped_column(String(4), nullable=True)
    expires_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expires_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    __table_args__ = (
        Index("ix_payment_tokens_tenant", "tenant_id"),
    )
