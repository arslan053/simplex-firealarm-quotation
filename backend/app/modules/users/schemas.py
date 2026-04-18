from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    role: str
    tenant_id: UUID | None = None
    is_active: bool
    must_change_password: bool
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class InviteUserRequest(BaseModel):
    email: str = Field(..., min_length=3)
    role: str = Field(default="employee", pattern=r"^(admin|employee)$")
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("first_name")
    @classmethod
    def first_name_no_spaces(cls, v: str) -> str:
        v = v.strip()
        if " " in v:
            raise ValueError("First name must be a single word (no spaces)")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_strip(cls, v: str) -> str:
        return v.strip()


class UpdateUserRequest(BaseModel):
    role: str = Field(..., pattern=r"^(admin|employee)$")
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)

    @field_validator("first_name")
    @classmethod
    def first_name_no_spaces(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if " " in v:
            raise ValueError("First name must be a single word (no spaces)")
        return v

    @field_validator("last_name")
    @classmethod
    def last_name_strip(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.strip()


class UserListResponse(BaseModel):
    items: list[UserResponse]
    total: int
