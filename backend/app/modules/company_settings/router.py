from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
    UserContext,
)

from .schemas import CompanySettingsResponse, TextSettingsRequest
from .service import CompanySettingsService

router = APIRouter(
    prefix="/api/settings/general",
    tags=["settings-general"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin"),
    ],
)


@router.get("", response_model=CompanySettingsResponse)
async def get_settings(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    service = CompanySettingsService(db)
    return await service.get_settings(tenant_id)


@router.put("", response_model=CompanySettingsResponse)
async def update_text_settings(
    request: Request,
    body: TextSettingsRequest,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    service = CompanySettingsService(db)
    return await service.update_text_settings(
        tenant_id,
        signatory_name=body.signatory_name,
        company_phone=body.company_phone,
    )


@router.post("/letterhead", response_model=CompanySettingsResponse)
async def upload_letterhead(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    file_bytes = await file.read()
    service = CompanySettingsService(db)
    return await service.upload_letterhead(tenant_id, file_bytes, file.filename or "")


@router.delete("/letterhead", response_model=CompanySettingsResponse)
async def delete_letterhead(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    service = CompanySettingsService(db)
    return await service.delete_letterhead(tenant_id)


@router.post("/signature", response_model=CompanySettingsResponse)
async def upload_signature(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    file_bytes = await file.read()
    service = CompanySettingsService(db)
    return await service.upload_signature(tenant_id, file_bytes, file.filename or "")


@router.delete("/signature", response_model=CompanySettingsResponse)
async def delete_signature(
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    service = CompanySettingsService(db)
    return await service.delete_signature(tenant_id)
