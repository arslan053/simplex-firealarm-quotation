from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
    UserContext,
)

from .schemas import PriceListResponse, PriceUpdateRequest, PriceUpdateResponse, UploadResponse
from .service import TenantPricingService

router = APIRouter(
    prefix="/api/settings/pricing",
    tags=["settings-pricing"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)


@router.get("", response_model=PriceListResponse)
async def get_price_list(
    request: Request,
    search: str | None = Query(default=None),
    category: str | None = Query(default=None),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = TenantPricingService(db)
    return await service.get_price_list(tenant_id, search=search, category=category)


@router.put("", response_model=PriceUpdateResponse)
async def update_prices(
    request: Request,
    body: PriceUpdateRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = TenantPricingService(db)
    return await service.update_prices(
        tenant_id,
        [item.model_dump() for item in body.items],
    )


@router.get("/categories")
async def get_categories(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    service = TenantPricingService(db)
    categories = await service.get_categories()
    return {"categories": categories}


@router.get("/template")
async def download_template(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = TenantPricingService(db)
    xlsx_bytes = await service.generate_template(tenant_id)

    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=price_list_template.xlsx"
        },
    )


@router.post("/upload", response_model=UploadResponse)
async def upload_template(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    file_bytes = await file.read()
    service = TenantPricingService(db)
    return await service.process_upload(tenant_id, file_bytes)
