import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.analysis.schemas import AnalysisResultResponse
from app.modules.analysis.service import AnalysisService
from app.modules.projects.models import Project
from app.modules.projects.service import ProjectService

router = APIRouter(prefix="/api/projects/{project_id}/analysis", tags=["analysis"])


async def _verify_project_ownership(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


@router.get(
    "/results",
    response_model=AnalysisResultResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_analysis_results(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = AnalysisService(db)
    return await service.get_results(tenant_id, project_id)


class ProtocolOverrideRequest(BaseModel):
    protocol: str


@router.put(
    "/protocol",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def override_protocol(
    project_id: uuid.UUID,
    body: ProtocolOverrideRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project_ownership(project_id, user, tenant_id, db)

    if body.protocol not in ("MX", "IDNET"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Protocol must be 'MX' or 'IDNET'.",
        )

    await db.execute(
        update(Project)
        .where(Project.id == project_id, Project.tenant_id == tenant_id)
        .values(protocol=body.protocol)
    )
    await db.commit()

    return {"protocol": body.protocol, "message": f"Protocol manually set to {body.protocol}."}
