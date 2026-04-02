import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.audit.service import AuditService
from app.modules.users.schemas import (
    InviteUserRequest,
    UpdateUserRequest,
    UserListResponse,
    UserResponse,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/api/tenant", tags=["tenant-users"])


@router.get(
    "/users",
    response_model=UserListResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def list_users(
    request: Request,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    tenant = request.state.tenant
    service = UserService(db)
    users, total = await service.list_users(uuid.UUID(tenant["id"]), skip=skip, limit=limit)
    return UserListResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.post(
    "/users/invite",
    response_model=UserResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def invite_user(
    body: InviteUserRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = request.state.tenant
    service = UserService(db)
    new_user = await service.invite_user(
        tenant_id=uuid.UUID(tenant["id"]),
        tenant_slug=tenant["slug"],
        data=body,
    )

    audit = AuditService(db)
    await audit.log_action(
        action="user.invited",
        entity_type="user",
        entity_id=str(new_user.id),
        tenant_id=uuid.UUID(tenant["id"]),
        actor_user_id=uuid.UUID(user.id),
        metadata_json={"email": body.email, "role": body.role},
    )

    return UserResponse.model_validate(new_user)


@router.patch(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = request.state.tenant
    service = UserService(db)
    updated_user = await service.update_user_role(user_id, uuid.UUID(tenant["id"]), body)

    audit = AuditService(db)
    await audit.log_action(
        action="user.role_updated",
        entity_type="user",
        entity_id=str(user_id),
        tenant_id=uuid.UUID(tenant["id"]),
        actor_user_id=uuid.UUID(user.id),
        metadata_json={"new_role": body.role},
    )

    return UserResponse.model_validate(updated_user)


@router.post(
    "/users/{user_id}/deactivate",
    response_model=UserResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tenant = request.state.tenant
    service = UserService(db)
    deactivated = await service.deactivate_user(
        user_id=user_id,
        tenant_id=uuid.UUID(tenant["id"]),
        actor_user_id=uuid.UUID(user.id),
    )

    audit = AuditService(db)
    await audit.log_action(
        action="user.deactivated",
        entity_type="user",
        entity_id=str(user_id),
        tenant_id=uuid.UUID(tenant["id"]),
        actor_user_id=uuid.UUID(user.id),
    )

    return UserResponse.model_validate(deactivated)
