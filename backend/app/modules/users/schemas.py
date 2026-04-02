from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: UUID
    email: str
    role: str
    tenant_id: UUID | None = None
    is_active: bool
    must_change_password: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InviteUserRequest(BaseModel):
    email: str = Field(..., min_length=3)
    role: str = Field(default="employee", pattern=r"^(admin|employee)$")


class UpdateUserRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|employee)$")


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
