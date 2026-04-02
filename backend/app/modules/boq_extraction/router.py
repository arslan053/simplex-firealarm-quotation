import asyncio
import logging
import uuid
from dataclasses import dataclass

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
from app.modules.boq_extraction.schemas import JobStartResponse, JobStatusResponse
from app.modules.boq_extraction.service import BoqExtractionService
from app.modules.projects.service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/boq-extraction",
    tags=["boq-extraction"],
)


@dataclass
class _JobEntry:
    status: str = "pending"
    message: str = "Queued"
    boq_items_count: int = 0


_jobs: dict[str, _JobEntry] = {}
_project_jobs: dict[str, str] = {}  # project_id → job_id


async def _run_background(
    job_id: str,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    entry = _jobs[job_id]
    entry.status = "running"
    entry.message = "Extracting BOQ items with GPT-5.2..."

    try:
        async with get_worker_db(str(tenant_id)) as db:
            service = BoqExtractionService(db)
            result = await service.run(tenant_id, project_id)
            entry.status = "success"
            entry.message = result.message
            entry.boq_items_count = result.boq_items_count
    except HTTPException as exc:
        entry.status = "failed"
        entry.message = exc.detail
        logger.error("BOQ extraction job %s failed: %s", job_id, exc.detail)
    except Exception as exc:
        entry.status = "failed"
        entry.message = f"Unexpected error: {str(exc)}"
        logger.exception("BOQ extraction job %s crashed", job_id)
    finally:
        _project_jobs.pop(str(project_id), None)


async def _verify_project(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


@router.post(
    "/run",
    response_model=JobStartResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def run_boq_extraction(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    job_id = str(uuid.uuid4())
    _jobs[job_id] = _JobEntry()
    _project_jobs[str(project_id)] = job_id

    asyncio.create_task(_run_background(job_id, tenant_id, project_id))

    return JobStartResponse(
        job_id=job_id,
        status="started",
        message="BOQ extraction started. Poll /status for progress.",
    )


@router.get(
    "/active-job",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_active_job(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    job_id = _project_jobs.get(str(project_id))
    if not job_id:
        return {"active": False}

    entry = _jobs.get(job_id)
    if not entry or entry.status not in ("pending", "running"):
        _project_jobs.pop(str(project_id), None)
        return {"active": False}

    return {"active": True, "job_id": job_id, "status": entry.status, "message": entry.message}


@router.get(
    "/status/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_status(
    project_id: uuid.UUID,
    job_id: str,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    entry = _jobs.get(job_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found.",
        )

    return JobStatusResponse(
        job_id=job_id,
        status=entry.status,
        message=entry.message,
        boq_items_count=entry.boq_items_count,
    )
