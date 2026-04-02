import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.boq.repository import DocumentRepository
from app.modules.boq.schemas import DocumentResponse, DocumentViewUrlResponse
from app.modules.projects.service import ProjectService
from app.shared.storage import get_file_url

router = APIRouter(prefix="/api/projects/{project_id}/documents", tags=["documents"])


async def _verify_project_ownership(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


@router.get(
    "",
    response_model=list[DocumentResponse],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def list_all_documents(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    repo = DocumentRepository(db)
    docs = await repo.get_all_by_project(tenant_id, project_id)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.get(
    "/{document_id}/view-url",
    response_model=DocumentViewUrlResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_document_view_url(
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    repo = DocumentRepository(db)
    doc = await repo.get_by_id(document_id, tenant_id, project_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    url = get_file_url(doc.object_key)
    return DocumentViewUrlResponse(url=url)
