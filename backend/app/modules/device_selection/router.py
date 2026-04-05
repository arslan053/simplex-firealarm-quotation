import asyncio
import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db, get_worker_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.device_selection.schemas import (
    DeviceSelectionItem,
    DeviceSelectionResultsResponse,
    JobStartResponse,
    JobStatusResponse,
    build_pagination,
)
from app.modules.device_selection.service import DeviceSelectionService
from app.modules.projects.models import Project
from app.modules.projects.service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/device-selection",
    tags=["device-selection"],
)


@dataclass
class _JobEntry:
    status: str = "pending"
    message: str = "Queued"
    matched_count: int = 0


_jobs: dict[str, _JobEntry] = {}
_project_jobs: dict[str, str] = {}  # project_id → job_id


async def _run_background(
    job_id: str,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    entry = _jobs[job_id]
    entry.status = "running"
    entry.message = "Matching BOQ items to devices with GPT-5.2..."

    try:
        async with get_worker_db(str(tenant_id)) as db:
            service = DeviceSelectionService(db)
            result = await service.run(tenant_id, project_id)
            entry.status = "success"
            entry.message = result.message
            entry.matched_count = result.matched_count
    except HTTPException as exc:
        entry.status = "failed"
        entry.message = exc.detail
        logger.error("Device selection job %s failed: %s", job_id, exc.detail)
    except Exception as exc:
        entry.status = "failed"
        entry.message = f"Unexpected error: {str(exc)}"
        logger.exception("Device selection job %s crashed", job_id)
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
async def run_device_selection(
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
        message="Device selection started. Poll /status for progress.",
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
        matched_count=entry.matched_count,
    )


@router.get(
    "/results",
    response_model=DeviceSelectionResultsResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_results(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    # Count total
    count_result = await db.execute(
        text("""
            SELECT count(*) FROM boq_device_selections
            WHERE tenant_id = :tid AND project_id = :pid
        """),
        {"tid": tenant_id, "pid": project_id},
    )
    total = count_result.scalar_one()

    # Fetch page
    offset = (page - 1) * limit
    rows_result = await db.execute(
        text("""
            SELECT
                ds.boq_item_id,
                bi.description AS boq_description,
                ds.selectable_id,
                s.category AS selectable_category,
                ds.selection_type,
                ds.product_codes,
                s.description AS selectable_description,
                ds.reason,
                ds.status
            FROM boq_device_selections ds
            JOIN boq_items bi ON bi.id = ds.boq_item_id
            LEFT JOIN selectables s ON s.id = ds.selectable_id
            WHERE ds.tenant_id = :tid AND ds.project_id = :pid
            ORDER BY bi.row_number ASC
            OFFSET :offset LIMIT :limit
        """),
        {"tid": tenant_id, "pid": project_id, "offset": offset, "limit": limit},
    )
    rows = rows_result.fetchall()

    items = [
        DeviceSelectionItem(
            boq_item_id=row.boq_item_id,
            boq_description=row.boq_description,
            selectable_id=row.selectable_id,
            selectable_category=row.selectable_category,
            selection_type=row.selection_type,
            product_codes=list(row.product_codes) if row.product_codes else [],
            selectable_description=row.selectable_description,
            reason=row.reason,
            status=row.status,
        )
        for row in rows
    ]

    # Fetch network_type from project
    proj_result = await db.execute(
        select(Project.network_type, Project.network_type_auto).where(
            Project.id == project_id,
            Project.tenant_id == tenant_id,
        )
    )
    proj_row = proj_result.first()

    return DeviceSelectionResultsResponse(
        project_id=project_id,
        data=items,
        pagination=build_pagination(page, limit, total),
        network_type=proj_row.network_type if proj_row else None,
        network_type_auto=proj_row.network_type_auto if proj_row else None,
    )


class NetworkTypeOverrideRequest(BaseModel):
    network_type: str


@router.put(
    "/network-type",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def override_network_type(
    project_id: uuid.UUID,
    body: NetworkTypeOverrideRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    if body.network_type not in ("wired", "fiber", "IP"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Network type must be 'wired', 'fiber', or 'IP'.",
        )

    await db.execute(
        update(Project)
        .where(Project.id == project_id, Project.tenant_id == tenant_id)
        .values(network_type=body.network_type)
    )
    await db.commit()

    return {"network_type": body.network_type, "message": f"Network type manually set to {body.network_type}."}
