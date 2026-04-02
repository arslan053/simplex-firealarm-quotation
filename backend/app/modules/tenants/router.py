import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_admin_domain,
    require_role,
)
from app.modules.audit.service import AuditService
from app.modules.tenants.schemas import (
    TenantCreate,
    TenantListResponse,
    TenantResolveResponse,
    TenantResponse,
    TenantUpdate,
    TenantWithStatsResponse,
)
from app.modules.tenants.service import TenantService
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserResponse

resolve_router = APIRouter(prefix="/api/tenants", tags=["tenants"])
admin_router = APIRouter(prefix="/api/admin", tags=["admin"])


@resolve_router.get("/resolve", response_model=TenantResolveResponse)
async def resolve_tenant(request: Request):
    tenant = getattr(request.state, "tenant", None)
    is_admin = getattr(request.state, "is_admin_domain", False)

    if is_admin:
        return TenantResolveResponse(is_admin_domain=True)

    if not tenant:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return TenantResolveResponse(
        id=tenant["id"],
        slug=tenant["slug"],
        name=tenant["name"],
        status=tenant["status"],
        settings_json=tenant.get("settings_json"),
    )


@admin_router.get(
    "/tenants",
    response_model=TenantListResponse,
    dependencies=[Depends(require_admin_domain), require_role("super_admin")],
)
async def list_tenants(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    tenants, total = await service.list_tenants(skip=skip, limit=limit)

    user_repo = UserRepository(db)
    tenant_ids = [t.id for t in tenants]
    user_counts = await user_repo.count_by_tenants(tenant_ids)

    items = []
    for t in tenants:
        data = TenantWithStatsResponse.model_validate(t)
        data.user_count = user_counts.get(t.id, 0)
        items.append(data)

    return TenantListResponse(items=items, total=total)


@admin_router.post(
    "/tenants",
    response_model=dict,
    dependencies=[Depends(require_admin_domain), require_role("super_admin")],
)
async def create_tenant(
    body: TenantCreate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    tenant, admin_user = await service.create_tenant(body)

    audit = AuditService(db)
    await audit.log_action(
        action="tenant.created",
        entity_type="tenant",
        entity_id=str(tenant.id),
        actor_user_id=uuid.UUID(user.id),
        metadata_json={"slug": tenant.slug, "admin_email": body.admin_email},
    )

    return {
        "tenant": TenantResponse.model_validate(tenant),
        "admin_user": UserResponse.model_validate(admin_user),
    }


@admin_router.get(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[Depends(require_admin_domain), require_role("super_admin")],
)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = TenantService(db)
    tenant = await service.get_tenant(tenant_id)
    return TenantResponse.model_validate(tenant)


@admin_router.delete(
    "/tenants/{tenant_id}",
    dependencies=[Depends(require_admin_domain), require_role("super_admin")],
)
async def delete_tenant(
    tenant_id: uuid.UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    await service.delete_tenant(tenant_id)

    audit = AuditService(db)
    await audit.log_action(
        action="tenant.deleted",
        entity_type="tenant",
        entity_id=str(tenant_id),
        actor_user_id=uuid.UUID(user.id),
    )

    return {"detail": "Tenant deleted"}


@admin_router.patch(
    "/tenants/{tenant_id}",
    response_model=TenantResponse,
    dependencies=[Depends(require_admin_domain), require_role("super_admin")],
)
async def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdate,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = TenantService(db)
    tenant = await service.update_tenant(tenant_id, body)

    audit = AuditService(db)
    await audit.log_action(
        action="tenant.updated",
        entity_type="tenant",
        entity_id=str(tenant.id),
        actor_user_id=uuid.UUID(user.id),
        metadata_json=body.model_dump(exclude_unset=True),
    )

    return TenantResponse.model_validate(tenant)


@admin_router.get(
    "/audit-logs",
    dependencies=[Depends(require_admin_domain), require_role("super_admin")],
)
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    audit = AuditService(db)
    logs = await audit.list_logs(skip=skip, limit=limit)
    return [
        {
            "id": str(log.id),
            "tenant_id": str(log.tenant_id) if log.tenant_id else None,
            "actor_user_id": str(log.actor_user_id) if log.actor_user_id else None,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "metadata_json": log.metadata_json,
            "created_at": str(log.created_at),
        }
        for log in logs
    ]
