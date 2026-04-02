import uuid
from typing import List

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
from app.modules.boq.schemas import (
    BoqItemListResponse,
    BoqItemResponse,
    DocumentResponse,
    ToggleHiddenRequest,
)
from app.modules.boq.service import BoqService

router = APIRouter(prefix="/api/projects/{project_id}/boq", tags=["boq"])


async def _verify_project_ownership(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    """Ensure user owns the project (same check as project update)."""
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def upload_boq(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    file: UploadFile = File(...),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = BoqService(db)
    return await service.upload_and_parse_boq(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=uuid.UUID(user.id),
        file=file,
    )


@router.get(
    "/items",
    response_model=BoqItemListResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def list_boq_items(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = BoqService(db)
    return await service.list_boq_items(tenant_id, project_id, page=page, limit=limit)


@router.patch(
    "/items/{item_id}/visibility",
    response_model=BoqItemResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def toggle_boq_item_visibility(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    body: ToggleHiddenRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = BoqService(db)
    return await service.toggle_boq_item_hidden(item_id, tenant_id, body.is_hidden)


@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def list_boq_documents(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = BoqService(db)
    return await service.list_documents(tenant_id, project_id)


@router.post(
    "/upload-pdf",
    response_model=DocumentResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def upload_boq_pdf(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    file: UploadFile = File(...),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = BoqService(db)
    return await service.upload_and_parse_boq_pdf(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=uuid.UUID(user.id),
        file=file,
    )


@router.post(
    "/upload-images",
    response_model=DocumentResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def upload_boq_images(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    files: List[UploadFile] = File(...),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = BoqService(db)
    return await service.upload_and_parse_boq_images(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=uuid.UUID(user.id),
        files=files,
    )
