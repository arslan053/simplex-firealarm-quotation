import uuid

from sqlalchemy import ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, UUIDPrimaryKey


class SpecBlock(Base, UUIDPrimaryKey):
    __tablename__ = "spec_blocks"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False
    )
    page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("spec_blocks.id"), nullable=True
    )
    order_in_page: Mapped[int] = mapped_column(Integer, nullable=False)
    style: Mapped[str] = mapped_column(Text, nullable=False)
    level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    list_kind: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_spec_blocks_doc_page", "document_id", "page_no"),
        Index("ix_spec_blocks_parent", "parent_id"),
    )
