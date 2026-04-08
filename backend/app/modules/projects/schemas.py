import math
from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=500)
    client_id: UUID
    country: str = Field(default="KSA", min_length=1, max_length=100)
    city: str = Field(..., min_length=1, max_length=200)
    due_date: date


class UpdateProjectRequest(BaseModel):
    project_name: str | None = Field(None, min_length=1, max_length=500)
    client_id: UUID | None = None
    country: str | None = Field(None, min_length=1, max_length=100)
    city: str | None = Field(None, min_length=1, max_length=200)
    due_date: date | None = None


class ProjectResponse(BaseModel):
    """Full project details — returned to project owner (employee)."""

    id: UUID
    tenant_id: UUID
    owner_user_id: UUID
    project_name: str
    client_id: UUID | None = None
    client_name: str | None = None
    country: str
    city: str
    due_date: date
    panel_family: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectAdminResponse(BaseModel):
    """Restricted view for admins — limited fields."""

    id: UUID
    project_name: str
    client_name: str | None = None
    status: str
    created_at: datetime | None = None
    created_by_name: str | None = None

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class ProjectListResponse(BaseModel):
    data: list[ProjectResponse]
    pagination: PaginationMeta


class ProjectAdminListResponse(BaseModel):
    data: list[ProjectAdminResponse]
    pagination: PaginationMeta


def build_pagination(page: int, limit: int, total: int) -> PaginationMeta:
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=math.ceil(total / limit) if limit > 0 else 0,
    )
