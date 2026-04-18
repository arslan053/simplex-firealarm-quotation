from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import UserContext, get_current_user
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MeResponse,
    MessageResponse,
    ResetPasswordRequest,
    TenantBrief,
    TokenResponse,
    UpdateProfileRequest,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    tenant = getattr(request.state, "tenant", None)
    is_admin = getattr(request.state, "is_admin_domain", False)

    service = AuthService(db)
    user, token = await service.authenticate(
        email=body.email,
        password=body.password,
        tenant_id=tenant["id"] if tenant else None,
        is_admin_domain=is_admin,
    )

    tenant_brief = None
    if user.tenant:
        tenant_brief = TenantBrief(id=user.tenant.id, slug=user.tenant.slug, name=user.tenant.name)

    return TokenResponse(
        access_token=token,
        user=MeResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            tenant_id=user.tenant_id,
            must_change_password=user.must_change_password,
            tenant=tenant_brief,
        ),
    )


@router.get("/me", response_model=MeResponse)
async def me(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    db_user = await service.get_me(user.id)

    tenant_brief = None
    if db_user.tenant:
        tenant_brief = TenantBrief(
            id=db_user.tenant.id, slug=db_user.tenant.slug, name=db_user.tenant.name
        )

    return MeResponse(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        role=db_user.role,
        tenant_id=db_user.tenant_id,
        must_change_password=db_user.must_change_password,
        tenant=tenant_brief,
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    await service.change_password(user.id, body.current_password, body.new_password)
    return MessageResponse(message="Password changed successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    tenant = getattr(request.state, "tenant", None)
    is_admin = getattr(request.state, "is_admin_domain", False)

    service = AuthService(db)
    await service.forgot_password(
        email=body.email,
        tenant_id=tenant["id"] if tenant else None,
        is_admin_domain=is_admin,
        tenant_slug=tenant["slug"] if tenant else None,
    )
    return MessageResponse(message="If an account exists with that email, you will receive a reset link.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.reset_password(body.token, body.new_password)
    return MessageResponse(message="Password has been reset successfully")


@router.patch("/profile", response_model=MeResponse)
async def update_profile(
    body: UpdateProfileRequest,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    db_user = await service.get_me(user.id)
    db_user.name = f"{body.first_name} {body.last_name}"
    await db.commit()
    await db.refresh(db_user)

    tenant_brief = None
    if db_user.tenant:
        tenant_brief = TenantBrief(
            id=db_user.tenant.id, slug=db_user.tenant.slug, name=db_user.tenant.name
        )

    return MeResponse(
        id=db_user.id,
        email=db_user.email,
        name=db_user.name,
        role=db_user.role,
        tenant_id=db_user.tenant_id,
        must_change_password=db_user.must_change_password,
        tenant=tenant_brief,
    )
