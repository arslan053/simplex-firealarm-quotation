from uuid import UUID

from pydantic import BaseModel, Field


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
    role: str
    tenant_id: UUID | None = None
    must_change_password: bool = False
    tenant: "TenantBrief | None" = None

    model_config = {"from_attributes": True}


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
