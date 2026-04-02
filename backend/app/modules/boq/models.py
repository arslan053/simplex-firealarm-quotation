from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin, UUIDPrimaryKey


class Document(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "documents"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    uploaded_by_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="BOQ")
    original_file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    document_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    document_category_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    project = relationship("Project", lazy="selectin")
    uploaded_by = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("ix_documents_tenant_id", "tenant_id"),
        Index("ix_documents_tenant_project", "tenant_id", "project_id"),
    )


class BoqItem(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "boq_items"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    project_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    document_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(15, 4), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False, default="boq_item")
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dimensions: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    document = relationship("Document", lazy="selectin")

    __table_args__ = (
        Index("ix_boq_items_tenant_id", "tenant_id"),
        Index("ix_boq_items_tenant_project", "tenant_id", "project_id"),
        Index("ix_boq_items_tenant_document", "tenant_id", "document_id"),
    )
