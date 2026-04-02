from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin, UUIDPrimaryKey


class Project(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "projects"

    tenant_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False
    )
    owner_user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    project_name: Mapped[str] = mapped_column(Text, nullable=False)
    client_name: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="KSA")
    city: Mapped[str] = mapped_column(String(200), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    panel_family: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None)
    protocol: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    protocol_auto: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    network_type: Mapped[str | None] = mapped_column(String(10), nullable=True, default=None)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="IN_PROGRESS"
    )

    owner = relationship("User", lazy="selectin")
    tenant = relationship("Tenant", lazy="selectin")

    __table_args__ = (
        Index("ix_projects_tenant_id", "tenant_id"),
        Index("ix_projects_tenant_owner", "tenant_id", "owner_user_id"),
        Index("ix_projects_tenant_created", "tenant_id", "created_at"),
    )
