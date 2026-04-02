from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
    UserContext,
)

from .schemas import PricingResponse
from .service import PricingService

router = APIRouter(
    prefix="/api/projects/{project_id}/pricing",
    tags=["pricing"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)


@router.post("/calculate", response_model=PricingResponse)
async def calculate_pricing(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = PricingService(db)
    return await service.calculate(tenant_id, pid)


@router.get("", response_model=PricingResponse)
async def get_pricing(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = PricingService(db)
    result = await service.get_pricing(tenant_id, pid)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pricing not calculated yet for this project.",
        )
    return result
