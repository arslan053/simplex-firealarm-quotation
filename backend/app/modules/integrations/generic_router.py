from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

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
    prefix="/api/integrations/generic",
    tags=["integrations-generic"],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)


class GenericStartQuotationResponse(BaseModel):
    status: str
    client_id: str
    project_id: str
    pipeline_run_id: str


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
        pass


@router.post("/quotation/start", response_model=GenericStartQuotationResponse)
async def start_generic_quotation(
    request: Request,
    boq_file: UploadFile = File(...),
    spec_file: UploadFile = File(...),
    source_platform: str = Form(...),
    platform_reply_info: str = Form("{}"),
    client_data: str = Form("{}"),
    project_data: str = Form("{}"),
    quotation_config: str = Form("{}"),
    boq_media_type: str = Form("xlsx"),
    callback_url: str = Form(""),
    boq_images: list[UploadFile] = File(default=[]),
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Generic multipart endpoint for any messaging platform.

    Accepts direct file uploads (BOQ + spec) plus metadata as form fields.
    Platform-specific n8n workflows download files themselves and POST here.
    """
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    user_id = uuid.UUID(user.id)

    # Parse JSON form fields
    try:
        reply_info = json.loads(platform_reply_info)
    except (json.JSONDecodeError, TypeError):
        reply_info = {}

    try:
        raw_client = json.loads(client_data)
    except (json.JSONDecodeError, TypeError):
        raw_client = {}

    try:
        raw_project = json.loads(project_data)
    except (json.JSONDecodeError, TypeError):
        raw_project = {}

    try:
        raw_cfg = json.loads(quotation_config)
    except (json.JSONDecodeError, TypeError):
        raw_cfg = {}

    # -------------------------
    # 1) Build defaults
    # -------------------------
    uid = uuid.uuid4().hex[:8]

    client_name = (raw_client.get("name") or "").strip()
    company_name = (raw_client.get("company_name") or "").strip()
    if not client_name:
        client_name = f"{source_platform.title()} Client {uid}"
    if not company_name:
        company_name = f"{source_platform.title()} Company {uid}"

    email = (raw_client.get("email") or "").strip() or None
    phone = (raw_client.get("phone") or "").strip() or None
    address = (raw_client.get("address") or "").strip() or "Riyadh"

    project_name = (raw_project.get("project_name") or "").strip() or f"{source_platform.title()} Project {uid}"
    city = (raw_project.get("city") or "").strip() or "Riyadh"
    country = (raw_project.get("country") or "").strip() or "KSA"
    due_date_raw = (raw_project.get("due_date") or "").strip()
    due_date = date.fromisoformat(due_date_raw) if due_date_raw else date.today()

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
    # 3) Upload BOQ/spec files
    # -------------------------
    if boq_media_type == "images":
        files_to_upload = boq_images if boq_images else [boq_file]
        await boq_service.upload_and_parse_boq_images(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            files=files_to_upload,
        )
    elif boq_media_type == "pdf":
        await boq_service.upload_and_parse_boq_pdf(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            file=boq_file,
        )
    else:
        await boq_service.upload_and_parse_boq(
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            file=boq_file,
        )

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
            "source_platform": source_platform,
            "platform_reply_info": reply_info,
            **({"callback_url": callback_url} if callback_url else {}),
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

    return GenericStartQuotationResponse(
        status="started",
        client_id=str(client.id),
        project_id=str(project_id),
        pipeline_run_id=str(run_id),
    )
