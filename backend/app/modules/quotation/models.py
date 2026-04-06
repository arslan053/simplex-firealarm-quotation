from __future__ import annotations

from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDPrimaryKey


class Quotation(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "quotations"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    generated_by_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    client_name: Mapped[str] = mapped_column(Text, nullable=False)
    client_address: Mapped[str] = mapped_column(Text, nullable=False)
    service_option: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    margin_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0.00
    )
    payment_terms_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    reference_number: Mapped[str] = mapped_column(Text, nullable=False)
    subtotal_sar: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    vat_sar: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    grand_total_sar: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)

    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        Index("uq_quotations_project", "tenant_id", "project_id", unique=True),
    )
