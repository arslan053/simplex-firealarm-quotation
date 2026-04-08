import math
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.projects.schemas import PaginationMeta, build_pagination  # noqa: F401


class CreateClientRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=500)
    company_name: str = Field(..., min_length=1, max_length=500)
    email: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=1000)


class UpdateClientRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=500)
    company_name: str | None = Field(None, min_length=1, max_length=500)
    email: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=1000)


class ClientResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    company_name: str
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ClientSearchItem(BaseModel):
    id: UUID
    name: str
    company_name: str

    model_config = {"from_attributes": True}


class ClientListResponse(BaseModel):
    data: list[ClientResponse]
    pagination: PaginationMeta
