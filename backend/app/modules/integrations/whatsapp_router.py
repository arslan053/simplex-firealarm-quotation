from __future__ import annotations

import asyncio
import uuid
from datetime import date
from tempfile import SpooledTemporaryFile
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_tenant_db, get_worker_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.clients.schemas import CreateClientRequest
from app.modules.clients.service import ClientService
from app.modules.boq.service import BoqService
from app.modules.pipeline.service import PipelineService
from app.modules.projects.schemas import CreateProjectRequest
from app.modules.projects.service import ProjectService
from app.modules.quotation.service import QuotationService
from app.modules.spec.service import SpecService

router = APIRouter(
    prefix="/api/integrations/whatsapp",
    tags=["integrations-whatsapp"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)


class WhatsappMediaItem(BaseModel):
    media_url: str
    mime_type: str | None = None
    filename: str | None = None


class WhatsappStartQuotationRequest(BaseModel):
    sender_phone: str = Field(..., min_length=1, max_length=100)
    chat_id: str | None = Field(default=None, max_length=255)

    boq_media_type: str = Field(..., pattern="^(xlsx|pdf|images)$")
    boq_media_url: str | None = None
    boq_filename: str | None = None
    boq_mime_type: str | None = None
    boq_images: list[WhatsappMediaItem] = []

    spec_media_url: str = Field(..., min_length=1)
    spec_filename: str | None = None

    client_data: dict = {}
    project_data: dict = {}
    quotation_config: dict = {}

    waha_api_key: str | None = None


class WhatsappStartQuotationResponse(BaseModel):
    status: str
    client_id: str
    project_id: str
    pipeline_run_id: str


def _normalize_media_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported media URL scheme: {parsed.scheme}",
        )

    host = parsed.hostname or ""
    if host in ("localhost", "127.0.0.1"):
        base = settings.WAHA_INTERNAL_URL.rstrip("/")
        return f"{base}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")
    return url


async def _download_waha_media(url: str, api_key: str) -> bytes:
    media_url = _normalize_media_url(url)
    headers = {"X-Api-Key": api_key} if api_key else {}
    timeout = httpx.Timeout(60.0, connect=10.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.get(media_url, headers=headers)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to download media from WAHA ({resp.status_code}).",
            )
        return resp.content


def _make_upload_file(filename: str, content: bytes, content_type: str | None = None) -> UploadFile:
    spooled = SpooledTemporaryFile(max_size=20 * 1024 * 1024)
    spooled.write(content)
    spooled.seek(0)
    headers = {"content-type": content_type} if content_type else None
    return UploadFile(file=spooled, filename=filename, headers=headers)


async def _run_pipeline_background(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    try:
        async with get_worker_db(str(tenant_id)) as db:
            service = PipelineService(db)
            await service.run_pipeline(run_id, tenant_id, project_id, user_id)
    except Exception:
        # Keep the endpoint fire-and-forget; PipelineService already marks failures.
        pass


@router.post("/quotation/start", response_model=WhatsappStartQuotationResponse)
async def start_whatsapp_quotation(
    body: WhatsappStartQuotationRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    user_id = uuid.UUID(user.id)

    # -------------------------
    # 1) Build defaults
    # -------------------------
    uid = uuid.uuid4().hex[:8]

    raw_client = body.client_data or {}
    client_name = (raw_client.get("name") or "").strip()
    company_name = (raw_client.get("company_name") or "").strip()
    if not client_name:
        client_name = f"WhatsApp Client {uid}"
    if not company_name:
        company_name = f"WhatsApp Company {uid}"

    email = (raw_client.get("email") or "").strip() or None
    phone = (raw_client.get("phone") or "").strip() or None
    address = (raw_client.get("address") or "").strip() or "Riyadh"

    raw_project = body.project_data or {}
    project_name = (raw_project.get("project_name") or "").strip() or f"WhatsApp Project {uid}"
    city = (raw_project.get("city") or "").strip() or "Riyadh"
    country = (raw_project.get("country") or "").strip() or "KSA"
    due_date_raw = (raw_project.get("due_date") or "").strip()
    due_date = date.fromisoformat(due_date_raw) if due_date_raw else date.today()

    raw_cfg = body.quotation_config or {}
    service_option = int(raw_cfg.get("service_option") or 1)
    if service_option not in (1, 2, 3):
        service_option = 1
    margin_percent = float(raw_cfg.get("margin_percent") or 0)
    payment_terms_text = raw_cfg.get("payment_terms_text") or None
    subject = raw_cfg.get("subject") or None

    # -------------------------
    # 2) Create client/project
    # -------------------------
    client_service = ClientService(db)
    project_service = ProjectService(db)
    boq_service = BoqService(db)
    spec_service = SpecService(db)
    pipeline_service = PipelineService(db)
    quotation_service = QuotationService(db)

    try:
        client = await client_service.create_client(
            tenant_id=tenant_id,
            data=CreateClientRequest(
                name=client_name,
                company_name=company_name,
                email=email,
                phone=phone,
                address=address,
            ),
        )
    except HTTPException as exc:
        if exc.status_code == 409:
            # Client already exists – look it up and reuse
            existing = await client_service.repo.find_by_company_name(
                tenant_id, company_name,
            )
            if not existing:
                raise
            client = existing
        else:
            raise

    project = await project_service.create_project(
        tenant_id=tenant_id,
        owner_user_id=user_id,
        data=CreateProjectRequest(
            project_name=project_name,
            client_id=client.id,
            city=city,
            country=country,
            due_date=due_date,
        ),
    )
    project_id = project.id

    # -------------------------
    # 3) Download/upload BOQ/spec
    # -------------------------
    waha_api_key = body.waha_api_key or settings.WAHA_API_KEY
    if not waha_api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WAHA API key missing for media download.",
        )

    if body.boq_media_type == "images":
        if not body.boq_images:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="BOQ images are required when boq_media_type is 'images'.",
            )
        img_files: list[UploadFile] = []
        for idx, img in enumerate(body.boq_images, start=1):
            img_bytes = await _download_waha_media(img.media_url, waha_api_key)
            mime = img.mime_type or "image/jpeg"
            ext = "png" if "png" in mime else "jpg"
            filename = img.filename or f"boq_image_{idx}.{ext}"
            img_files.append(_make_upload_file(filename, img_bytes, mime))
        await boq_service.upload_and_parse_boq_images(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            files=img_files,
        )
    else:
        if not body.boq_media_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="BOQ media URL is required for xlsx/pdf uploads.",
            )
        boq_bytes = await _download_waha_media(body.boq_media_url, waha_api_key)
        if body.boq_media_type == "pdf":
            boq_filename = body.boq_filename or "boq.pdf"
            boq_file = _make_upload_file(boq_filename, boq_bytes, "application/pdf")
            await boq_service.upload_and_parse_boq_pdf(
                tenant_id=tenant_id,
                project_id=project_id,
                user_id=user_id,
                file=boq_file,
            )
        else:
            boq_filename = body.boq_filename or "boq.xlsx"
            boq_mime = body.boq_mime_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            boq_file = _make_upload_file(boq_filename, boq_bytes, boq_mime)
            await boq_service.upload_and_parse_boq(
                tenant_id=tenant_id,
                project_id=project_id,
                user_id=user_id,
                file=boq_file,
            )

    spec_bytes = await _download_waha_media(body.spec_media_url, waha_api_key)
    spec_filename = body.spec_filename or "specification.pdf"
    spec_file = _make_upload_file(spec_filename, spec_bytes, "application/pdf")
    await spec_service.upload_and_start(
        tenant_id=tenant_id,
        project_id=project_id,
        user_id=user_id,
        file=spec_file,
    )

    # -------------------------
    # 4) Save quotation config
    # -------------------------
    questions = await quotation_service.get_inclusion_questions(
        tenant_id=tenant_id,
        project_id=project_id,
        service_option=service_option,
    )
    inclusion_answers: dict[str, bool] = {}
    for q in questions:
        key = q.get("key") if isinstance(q, dict) else getattr(q, "key", None)
        if key:
            inclusion_answers[str(key)] = False

    await pipeline_service.save_quotation_config(
        tenant_id=tenant_id,
        project_id=project_id,
        config={
            "client_name": client_name,
            "client_address": address or company_name,
            "subject": subject,
            "service_option": service_option,
            "margin_percent": margin_percent,
            "payment_terms_text": payment_terms_text,
            "inclusion_answers": inclusion_answers,
            "source_platform": "whatsapp",
            "platform_reply_info": {
                "sender_phone": body.sender_phone,
                "chat_id": body.chat_id,
            },
        },
    )

    # -------------------------
    # 5) Start pipeline async
    # -------------------------
    await pipeline_service.validate_can_start(tenant_id, project_id)
    run_id = await pipeline_service.create_run(tenant_id, project_id, user_id)
    asyncio.create_task(
        _run_pipeline_background(
            run_id=run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
        )
    )

    return WhatsappStartQuotationResponse(
        status="started",
        client_id=str(client.id),
        project_id=str(project_id),
        pipeline_run_id=str(run_id),
    )
