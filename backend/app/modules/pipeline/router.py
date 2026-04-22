import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db, get_worker_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.projects.service import ProjectService
from app.modules.pipeline.schemas import (
    OverridesRequest,
    PipelineStatusResponse,
    QuotationConfigRequest,
    QuotationConfigResponse,
    StartPipelineResponse,
)
from app.modules.pipeline.service import PipelineService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/pipeline",
    tags=["pipeline"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)


async def _verify_project(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


async def _run_pipeline_background(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    resume_from: str | None = None,
) -> None:
    try:
        async with get_worker_db(str(tenant_id)) as db:
            service = PipelineService(db)
            await service.run_pipeline(
                run_id, tenant_id, project_id, user_id,
                resume_from=resume_from,
            )
    except Exception as exc:
        logger.exception("Pipeline background task crashed: %s", exc)


# ------------------------------------------------------------------
# POST /run — start pipeline
# ------------------------------------------------------------------


@router.post("/run", response_model=StartPipelineResponse)
async def start_pipeline(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    service = PipelineService(db)
    await service.validate_can_start(tenant_id, project_id)

    run_id = await service.create_run(tenant_id, project_id, uuid.UUID(user.id))

    asyncio.create_task(
        _run_pipeline_background(run_id, tenant_id, project_id, uuid.UUID(user.id))
    )

    return StartPipelineResponse(
        pipeline_run_id=str(run_id),
        status="started",
    )


# ------------------------------------------------------------------
# GET /status — poll pipeline status
# ------------------------------------------------------------------


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    service = PipelineService(db)
    run = await service.get_latest_run(tenant_id, project_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pipeline run found for this project.",
        )

    return PipelineStatusResponse(**run)


# ------------------------------------------------------------------
# POST /retry — resume from failed step
# ------------------------------------------------------------------


@router.post("/retry", response_model=StartPipelineResponse)
async def retry_pipeline(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    service = PipelineService(db)
    run = await service.get_latest_run(tenant_id, project_id)
    if not run or run["status"] != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No failed pipeline to retry.",
        )

    run_id = uuid.UUID(run["id"])
    resume_from = run["error_step"]

    # Reset error state
    await service._update_run(
        run_id,
        status="running",
        error_message=None,
        error_step=None,
    )

    asyncio.create_task(
        _run_pipeline_background(
            run_id, tenant_id, project_id, uuid.UUID(user.id),
            resume_from=resume_from,
        )
    )

    return StartPipelineResponse(
        pipeline_run_id=str(run_id),
        status="resumed",
    )


# ------------------------------------------------------------------
# POST /quotation-config — save quotation inputs
# ------------------------------------------------------------------


@router.post("/quotation-config", response_model=QuotationConfigResponse)
async def save_quotation_config(
    project_id: uuid.UUID,
    body: QuotationConfigRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    service = PipelineService(db)
    config = await service.save_quotation_config(
        tenant_id, project_id, body.model_dump()
    )
    return QuotationConfigResponse(quotation_config=config)


@router.get("/quotation-config", response_model=QuotationConfigResponse)
async def get_quotation_config(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    service = PipelineService(db)
    config = await service.get_quotation_config(tenant_id, project_id)
    return QuotationConfigResponse(quotation_config=config or {})


# ------------------------------------------------------------------
# PATCH /overrides — save optional overrides
# ------------------------------------------------------------------


@router.patch("/overrides", response_model=OverridesRequest)
async def save_overrides(
    project_id: uuid.UUID,
    body: OverridesRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    service = PipelineService(db)
    result = await service.save_overrides(
        tenant_id, project_id,
        body.protocol, body.notification_type, body.network_type,
    )
    return result
