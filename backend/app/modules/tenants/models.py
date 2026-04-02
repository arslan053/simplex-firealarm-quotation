from sqlalchemy import Index, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin, UUIDPrimaryKey


class Tenant(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(String(63), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    settings_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    users = relationship("User", back_populates="tenant", lazy="selectin")
