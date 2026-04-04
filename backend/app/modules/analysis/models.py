import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin, UUIDPrimaryKey


class AnalysisAnswer(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "analysis_answers"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prompt_questions.id"), nullable=False
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    supporting_notes: Mapped[str] = mapped_column(Text, nullable=False)
    inferred_from: Mapped[str] = mapped_column(String(10), nullable=False)

    __table_args__ = (
        Index("ix_analysis_answers_tenant_id", "tenant_id"),
        Index("ix_analysis_answers_tenant_project", "tenant_id", "project_id"),
    )
