"""API router for panel selection."""

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db, get_worker_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.panel_selection.schemas import (
    GateResult,
    JobStartResponse,
    JobStatusResponse,
    PanelAnswersResponse,
    PanelGroupProduct,
    PanelGroupResult,
    PanelProduct,
    PanelQuestionAnswer,
    PanelSelectionResultsResponse,
)
from app.modules.panel_selection.service import (
    PANEL_CONFIGS,
    PanelSelectionService,
    determine_panel_type,
)
from app.modules.projects.service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/panel-selection",
    tags=["panel-selection"],
)


@dataclass
class _JobEntry:
    status: str = "pending"
    message: str = "Queued"
    result: dict = field(default_factory=dict)


_jobs: dict[str, _JobEntry] = {}
_project_jobs: dict[str, str] = {}  # project_id → job_id


async def _run_background(
    job_id: str,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    entry = _jobs[job_id]
    entry.status = "running"
    entry.message = "Analyzing BOQ for panel configuration..."

    try:
        async with get_worker_db(str(tenant_id)) as db:
            service = PanelSelectionService(db)
            result = await service.run(tenant_id, project_id)
            entry.status = "success"
            entry.message = result["message"]
            entry.result = result
    except HTTPException as exc:
        entry.status = "failed"
        entry.message = exc.detail
        logger.error("Panel selection job %s failed: %s", job_id, exc.detail)
    except Exception as exc:
        entry.status = "failed"
        entry.message = f"Unexpected error: {str(exc)}"
        logger.exception("Panel selection job %s crashed", job_id)
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
async def run_panel_selection(
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
        message="Panel selection started. Poll /status for progress.",
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
    )


@router.get(
    "/results",
    response_model=PanelSelectionResultsResponse,
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
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    # Query panel_selections
    rows_result = await db.execute(text("""
        SELECT product_code, product_name, quantity, source, question_no, reason,
               panel_group_id
        FROM panel_selections
        WHERE tenant_id = :tid AND project_id = :pid
        ORDER BY created_at ASC
    """), {"tid": tenant_id, "pid": project_id})
    rows = rows_result.fetchall()

    if not rows:
        return PanelSelectionResultsResponse(
            project_id=project_id,
            panel_supported=False,
            gate_result=GateResult(
                q1_total_devices=0,
                q1_devices_per_panel=0,
                q1_panel_count=None,
                q1_passed=False,
                q2_passed=True,
                q3_passed=True,
            ),
            products=[],
            status="empty",
            message="Panel selection has not been run yet.",
        )

    # Check if it's a gate fail
    is_gate_fail = any(r.source == "gate_fail" for r in rows)

    if is_gate_fail:
        fail_row = next(r for r in rows if r.source == "gate_fail")
        gate_result = await _build_gate_result(db, tenant_id, project_id, rows)
        return PanelSelectionResultsResponse(
            project_id=project_id,
            panel_supported=False,
            gate_result=gate_result,
            products=[],
            status="success",
            message=f"Panel not supported: {fail_row.reason}",
        )

    # Build flat products list (always present for backward compat)
    products = [
        PanelProduct(
            product_code=r.product_code,
            product_name=r.product_name,
            quantity=r.quantity,
            source=r.source,
            question_no=r.question_no,
            reason=r.reason,
        )
        for r in rows
    ]

    # Detect multi-group mode
    is_multi_group = any(r.panel_group_id is not None for r in rows)
    panel_groups_out: list[PanelGroupResult] = []

    if is_multi_group:
        pg_result = await db.execute(text("""
            SELECT id, description, loop_count, quantity, panel_type, is_main
            FROM panel_groups
            WHERE tenant_id = :tid AND project_id = :pid
            ORDER BY is_main DESC, loop_count DESC
        """), {"tid": tenant_id, "pid": project_id})
        pg_rows = pg_result.fetchall()

        for pg in pg_rows:
            gid = str(pg.id)
            panel_label = (
                PANEL_CONFIGS[pg.panel_type]["label"]
                if pg.panel_type in PANEL_CONFIGS
                else pg.panel_type
            )
            group_products = [
                PanelGroupProduct(
                    product_code=r.product_code,
                    product_name=r.product_name,
                    quantity=r.quantity,
                    source=r.source,
                    question_no=r.question_no,
                    reason=r.reason,
                )
                for r in rows
                if str(r.panel_group_id) == gid
            ]
            panel_groups_out.append(PanelGroupResult(
                id=gid,
                boq_description=pg.description,
                loop_count=pg.loop_count,
                quantity=pg.quantity,
                panel_type=pg.panel_type,
                panel_label=panel_label,
                is_main=pg.is_main,
                products=group_products,
            ))

    gate_result = await _build_gate_result(db, tenant_id, project_id, rows)
    panel_label = gate_result.panel_label or "Panel"

    return PanelSelectionResultsResponse(
        project_id=project_id,
        panel_supported=True,
        gate_result=gate_result,
        products=products,
        is_multi_group=is_multi_group,
        panel_groups=panel_groups_out,
        status="success",
        message=f"{panel_label} configuration complete. {len(products)} products selected.",
    )


@router.get(
    "/answers",
    response_model=PanelAnswersResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_answers(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    await _verify_project(project_id, user, tenant_id, db)

    result = await db.execute(text("""
        SELECT pq.question_no, pq.question, aa.answer, aa.confidence, aa.supporting_notes
        FROM analysis_answers aa
        JOIN prompt_questions pq ON pq.id = aa.question_id
        WHERE aa.tenant_id = :tid
          AND aa.project_id = :pid
          AND pq.category IN ('4007_panel_questions', '4100ES_panel_questions', 'multi_panel_questions')
        ORDER BY pq.question_no ASC
    """), {"tid": tenant_id, "pid": project_id})
    rows = result.fetchall()

    answers = []
    for row in rows:
        notes_raw = row.supporting_notes or ""
        notes = [n.strip() for n in notes_raw.split("\n") if n.strip()] if notes_raw else []
        answers.append(PanelQuestionAnswer(
            question_no=row.question_no,
            question=row.question,
            answer=row.answer,
            confidence=row.confidence,
            supporting_notes=notes,
        ))

    return PanelAnswersResponse(answers=answers)


async def _build_gate_result(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    stored_rows: list | None = None,
) -> GateResult:
    """Reconstruct gate result from DB for the results endpoint."""

    # Detect multi-group mode by checking panel_groups table
    mg_result = await db.execute(text("""
        SELECT id, panel_type, is_main, loop_count, quantity
        FROM panel_groups
        WHERE tenant_id = :tid AND project_id = :pid
        ORDER BY is_main DESC
        LIMIT 1
    """), {"tid": tenant_id, "pid": project_id})
    mg_main = mg_result.first()

    if mg_main:
        # Multi-group: use main panel's type for gate result
        main_type = mg_main.panel_type
        main_label = (
            PANEL_CONFIGS[main_type]["label"]
            if main_type in PANEL_CONFIGS
            else main_type
        )
        # Get total panel count from all groups
        pc_result = await db.execute(text("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM panel_groups
            WHERE tenant_id = :tid AND project_id = :pid
        """), {"tid": tenant_id, "pid": project_id})
        total_panel_count = int(pc_result.scalar_one())

        # Get device count
        dev_result = await db.execute(text("""
            SELECT COALESCE(SUM(bi.quantity), 0) AS total
            FROM boq_device_selections ds
            JOIN boq_items bi ON bi.id = ds.boq_item_id
            JOIN selectables s ON s.id = ds.selectable_id
            WHERE ds.tenant_id = :tid
              AND ds.project_id = :pid
              AND s.category IN ('mx_detection_device', 'idnet_detection_device')
        """), {"tid": tenant_id, "pid": project_id})
        total_devices = int(dev_result.scalar_one())

        return GateResult(
            q1_total_devices=total_devices,
            q1_devices_per_panel=total_devices,
            q1_panel_count=total_panel_count,
            q1_passed=True,
            panel_type=main_type,
            panel_label=main_label,
            mx_addressable_blocked=False,
            q2_answer="No",
            q2_passed=True,
            q3_answer="No",
            q3_passed=True,
            is_4100es=main_type == "4100ES",
            entry_reasons=[],
            loop_count=mg_main.loop_count,
        )

    # Detect 4100ES by checking if stored products have step_* sources
    is_4100es = False
    if stored_rows:
        is_4100es = any(
            r.source.startswith("step_")
            for r in stored_rows
            if r.source
        )

    # Count detection devices
    dev_result = await db.execute(text("""
        SELECT COALESCE(SUM(bi.quantity), 0) AS total
        FROM boq_device_selections ds
        JOIN boq_items bi ON bi.id = ds.boq_item_id
        JOIN selectables s ON s.id = ds.selectable_id
        WHERE ds.tenant_id = :tid
          AND ds.project_id = :pid
          AND s.category IN ('mx_detection_device', 'idnet_detection_device')
    """), {"tid": tenant_id, "pid": project_id})
    total_devices = int(dev_result.scalar_one())

    # Get panel count from panel analysis (Q101/Q102 multi-panel)
    panel_count = None
    pa_result = await db.execute(text("""
        SELECT pq.question_no, aa.answer
        FROM analysis_answers aa
        JOIN prompt_questions pq ON pq.id = aa.question_id
        WHERE aa.tenant_id = :tid
          AND aa.project_id = :pid
          AND pq.category = 'Panel_selection'
          AND pq.question_no IN (101, 102)
    """), {"tid": tenant_id, "pid": project_id})
    pa_answers = {row.question_no: row.answer for row in pa_result.fetchall()}
    if pa_answers.get(101) == "Yes" or pa_answers.get(102) == "Yes":
        pc_result = await db.execute(text("""
            SELECT COALESCE(SUM(quantity), 0)
            FROM boq_items
            WHERE tenant_id = :tid AND project_id = :pid
              AND category = 'panel' AND is_hidden = false
        """), {"tid": tenant_id, "pid": project_id})
        pc = int(pc_result.scalar_one())
        if pc > 0:
            panel_count = pc

    devices_per_panel = (
        total_devices // panel_count if panel_count and panel_count > 0
        else total_devices
    )

    # Get Q2, Q3, Q21 answers from analysis_answers
    q2_answer = None
    q3_answer = None
    q21_raw = None
    ans_result = await db.execute(text("""
        SELECT pq.question_no, aa.answer
        FROM analysis_answers aa
        JOIN prompt_questions pq ON pq.id = aa.question_id
        WHERE aa.tenant_id = :tid
          AND aa.project_id = :pid
          AND pq.category IN ('4007_panel_questions', 'multi_panel_questions')
          AND pq.question_no IN (2, 3, 21)
    """), {"tid": tenant_id, "pid": project_id})
    for row in ans_result.fetchall():
        if row.question_no == 2:
            q2_answer = row.answer
        elif row.question_no == 3:
            q3_answer = row.answer
        elif row.question_no == 21:
            q21_raw = row.answer

    # Parse loop count (Q21) — null means not specified
    loop_count: int | None = None
    if q21_raw and str(q21_raw).lower() not in ("null", "none", "n/a", ""):
        try:
            loop_count = max(0, int(re.sub(r"[^\d]", "", str(q21_raw)))) or None
        except (ValueError, TypeError):
            loop_count = None

    if is_4100es:
        # Reconstruct entry reasons
        entry_reasons: list[str] = []
        if devices_per_panel >= 1000:
            entry_reasons.append(f"{devices_per_panel} devices/panel >= 1000")
        if q2_answer == "Yes":
            entry_reasons.append("speakers required")
        if q3_answer == "Yes":
            entry_reasons.append("telephone required")
        if loop_count is not None and loop_count > 6:
            entry_reasons.append(f"loop count {loop_count} > 6")

        return GateResult(
            q1_total_devices=total_devices,
            q1_devices_per_panel=devices_per_panel,
            q1_panel_count=panel_count,
            q1_passed=True,
            panel_type="4100ES",
            panel_label="4100ES",
            mx_addressable_blocked=False,
            q2_answer=q2_answer,
            q2_passed=True,
            q3_answer=q3_answer,
            q3_passed=True,
            is_4100es=True,
            entry_reasons=entry_reasons,
            loop_count=loop_count,
        )

    # Existing 4007/4010 path
    panel_type, panel_label = determine_panel_type(devices_per_panel)

    # Loop count override: if loops > 2 but device range says 4007, upgrade to 4010
    if loop_count is not None and loop_count > 2 and panel_type == "4007":
        panel_type = "4010_1bay"
        panel_label = PANEL_CONFIGS["4010_1bay"]["label"]

    # Check MX + addressable block
    mx_addressable_blocked = False
    if panel_type and not PANEL_CONFIGS[panel_type]["supports_mx_addressable"]:
        proto_result = await db.execute(text(
            "SELECT protocol FROM projects WHERE id = :pid AND tenant_id = :tid"
        ), {"tid": tenant_id, "pid": project_id})
        protocol_row = proto_result.first()
        is_mx = protocol_row and protocol_row.protocol == "MX"

        if is_mx:
            notif_result = await db.execute(text("""
                SELECT DISTINCT s.category
                FROM boq_device_selections ds
                JOIN selectables s ON s.id = ds.selectable_id
                WHERE ds.tenant_id = :tid
                  AND ds.project_id = :pid
                  AND s.category IN (
                      'addressable_notification_device',
                      'non_addressable_notification_device'
                  )
            """), {"tid": tenant_id, "pid": project_id})
            notif_cats = [row[0] for row in notif_result.fetchall()]
            is_addressable = (
                "addressable_notification_device" in notif_cats
                and "non_addressable_notification_device" not in notif_cats
            )
            mx_addressable_blocked = is_addressable

    return GateResult(
        q1_total_devices=total_devices,
        q1_devices_per_panel=devices_per_panel,
        q1_panel_count=panel_count,
        q1_passed=panel_type is not None,
        panel_type=panel_type,
        panel_label=panel_label,
        mx_addressable_blocked=mx_addressable_blocked,
        q2_answer=q2_answer,
        q2_passed=q2_answer != "Yes" if q2_answer else True,
        q3_answer=q3_answer,
        q3_passed=q3_answer != "Yes" if q3_answer else True,
        loop_count=loop_count,
    )
