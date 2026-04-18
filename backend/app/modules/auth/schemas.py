from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "MeResponse"


class MeResponse(BaseModel):
    id: UUID
    email: str
    name: str | None = None
    role: str
    tenant_id: UUID | None = None
    must_change_password: bool = False
    tenant: "TenantBrief | None" = None

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
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


class TenantBrief(BaseModel):
    id: UUID
    slug: str
    name: str

    model_config = {"from_attributes": True}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=1)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8)


class MessageResponse(BaseModel):
    message: str
