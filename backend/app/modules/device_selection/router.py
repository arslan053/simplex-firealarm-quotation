import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
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
    build_pagination,
)
from app.modules.projects.models import Project
from app.modules.projects.service import ProjectService

router = APIRouter(
    prefix="/api/projects/{project_id}/device-selection",
    tags=["device-selection"],
)


async def _verify_project(
    project_id: uuid.UUID,
    user: UserContext,
    tenant_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    svc = ProjectService(db)
    await svc.get_own_project(project_id, uuid.UUID(user.id), tenant_id)


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

    # Fetch project-level overrides
    proj_result = await db.execute(
        select(
            Project.network_type,
            Project.network_type_auto,
            Project.notification_type,
            Project.notification_type_auto,
        ).where(
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
        notification_type=proj_row.notification_type if proj_row else None,
        notification_type_auto=proj_row.notification_type_auto if proj_row else None,
    )
