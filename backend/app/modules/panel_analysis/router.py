import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.panel_analysis.schemas import PanelAnalysisResultResponse
from app.modules.panel_analysis.service import PanelAnalysisService
from app.modules.projects.service import ProjectService

router = APIRouter(prefix="/api/projects/{project_id}/panel-analysis", tags=["panel-analysis"])


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
    response_model=PanelAnalysisResultResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_panel_analysis_results(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    await _verify_project_ownership(project_id, user, tenant_id, db)

    service = PanelAnalysisService(db)
    return await service.get_results(tenant_id, project_id)
