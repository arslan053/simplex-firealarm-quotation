from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=63, pattern=r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
    admin_email: str = Field(..., min_length=3)


class TenantUpdate(BaseModel):
    name: str | None = None
    status: str | None = Field(None, pattern=r"^(active|suspended)$")
    settings_json: dict | None = None


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    settings_json: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TenantResolveResponse(BaseModel):
    id: UUID | None = None
    slug: str | None = None
    name: str | None = None
    status: str | None = None
    settings_json: dict | None = None
    is_admin_domain: bool = False


class TenantWithStatsResponse(TenantResponse):
    user_count: int = 0


class TenantListResponse(BaseModel):
    items: list[TenantWithStatsResponse]
    total: int
