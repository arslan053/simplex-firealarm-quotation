import uuid

from fastapi import APIRouter, Depends, Query, Request, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.projects.service import ProjectService
from app.modules.spec.schemas import (
    SpecBlockListResponse,
    SpecExistingCheckResponse,
    SpecUploadResponse,
)
from app.modules.spec.service import SpecService

router = APIRouter(prefix="/api/projects/{project_id}/spec", tags=["spec"])


async def _verify_project_ownership(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Ensure user owns the project (same check as project update)."""
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


@router.get(
    "/check",
    response_model=SpecExistingCheckResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def check_existing_spec(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = SpecService(db)
    return await service.check_existing(tenant_id, project_id)


@router.post(
    "/upload",
    response_model=SpecUploadResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def upload_spec(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    file: UploadFile = File(...),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = SpecService(db)
    return await service.upload_and_start(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=uuid.UUID(user.id),
        file=file,
    )


@router.get(
    "/blocks",
    response_model=SpecBlockListResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_spec_blocks(
    project_id: uuid.UUID,
    request: Request,
    document_id: uuid.UUID = Query(...),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = SpecService(db)
    return await service.list_spec_blocks(tenant_id, document_id, page, limit)
