from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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

from .schemas import (
    GenerateQuotationRequest,
    InclusionQuestionsResponse,
    QuotationDownloadResponse,
    QuotationResponse,
)
from .service import QuotationService

router = APIRouter(
    prefix="/api/projects/{project_id}/quotation",
    tags=["quotation"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)


@router.get("/inclusions", response_model=InclusionQuestionsResponse)
async def get_inclusions(
    project_id: str,
    request: Request,
    service_option: int = Query(ge=1, le=3),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = QuotationService(db)
    questions = await service.get_inclusion_questions(tenant_id, pid, service_option)
    return InclusionQuestionsResponse(questions=questions)


@router.post("/generate", response_model=QuotationResponse)
async def generate_quotation(
    project_id: str,
    body: GenerateQuotationRequest,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)
    uid = uuid.UUID(user.id)

    service = QuotationService(db)
    return await service.generate(tenant_id, pid, uid, body)


@router.get("", response_model=QuotationResponse)
async def get_quotation(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = QuotationService(db)
    result = await service.get_quotation(tenant_id, pid)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quotation generated yet for this project.",
        )
    return result


@router.get("/download", response_model=QuotationDownloadResponse)
async def download_quotation(
    project_id: str,
    request: Request,
    format: str = Query("docx", pattern="^(docx|xlsx)$"),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = QuotationService(db)
    result = await service.get_download_url(tenant_id, pid, fmt=format)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quotation found for this project.",
        )
    return result


@router.get("/download-file")
async def download_quotation_file(
    project_id: str,
    request: Request,
    format: str = Query("docx", pattern="^(docx|xlsx)$"),
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    """Return the actual quotation file bytes for direct download."""
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = QuotationService(db)
    file_data = await service.get_file_bytes(tenant_id, pid, fmt=format)
    if file_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quotation found for this project.",
        )
    file_bytes, file_name = file_data
    if format == "xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/preview")
async def preview_quotation(
    project_id: str,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
    user: UserContext = Depends(get_current_user),
):
    """Return the quotation as an inline PDF for browser viewing."""
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    pid = uuid.UUID(project_id)

    service = QuotationService(db)
    pdf_bytes = await service.get_preview_pdf(tenant_id, pid)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No quotation found for this project.",
        )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=quotation.pdf"},
    )
