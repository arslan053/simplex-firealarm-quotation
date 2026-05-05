from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.boq_extraction.service import BoqExtractionService
from app.modules.spec_analysis.service import SpecAnalysisService
from app.modules.device_selection.service import DeviceSelectionService
from app.modules.panel_selection.service import PanelSelectionService
from app.modules.pricing.service import PricingService
from app.modules.quotation.schemas import GenerateQuotationRequest
from app.modules.quotation.service import QuotationService

logger = logging.getLogger(__name__)

STEPS = [
    "boq_extraction",
    "spec_analysis",
    "device_selection",
    "panel_selection",
    "pricing",
    "quotation_generation",
]

STEP_TIMEOUT_SECONDS = {
    "boq_extraction": 15 * 60,
    "spec_analysis": 15 * 60,
    "device_selection": 15 * 60,
    "panel_selection": 15 * 60,
    "pricing": 2 * 60,
    "quotation_generation": 2 * 60,
}

STEP_LABELS = {
    "boq_extraction": "BOQ extraction",
    "spec_analysis": "specification analysis",
    "device_selection": "device selection",
    "panel_selection": "panel selection",
    "pricing": "pricing calculation",
    "quotation_generation": "quotation generation",
    "pipeline": "pipeline",
}


def _step_label(step: str) -> str:
    return STEP_LABELS.get(step, step.replace("_", " "))


def _error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str) and detail.strip():
            return detail.strip()
        if detail is not None:
            try:
                return json.dumps(detail)
            except TypeError:
                return str(detail)

    message = str(exc).strip()
    return message or "Pipeline step failed. Please retry."


class PipelineService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Pipeline run CRUD
    # ------------------------------------------------------------------

    async def create_run(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> uuid.UUID:
        run_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text("""
                INSERT INTO pipeline_runs
                    (id, tenant_id, project_id, user_id, status, steps_completed,
                     retry_count, started_at, created_at, updated_at)
                VALUES
                    (:id, :tid, :pid, :uid, 'running', '[]'::jsonb,
                     0, :now, :now, :now)
            """),
            {
                "id": run_id,
                "tid": tenant_id,
                "pid": project_id,
                "uid": user_id,
                "now": now,
            },
        )
        await self.db.commit()
        return run_id

    async def get_latest_run(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict | None:
        result = await self.db.execute(
            text("""
                SELECT id, status, current_step, steps_completed,
                       error_message, error_step, retry_count,
                       started_at, completed_at, updated_at
                FROM pipeline_runs
                WHERE tenant_id = :tid AND project_id = :pid
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row:
            return None
        return {
            "id": str(row[0]),
            "status": row[1],
            "current_step": row[2],
            "steps_completed": row[3] or [],
            "error_message": row[4],
            "error_step": row[5],
            "retry_count": row[6],
            "started_at": row[7].isoformat() if row[7] else None,
            "completed_at": row[8].isoformat() if row[8] else None,
            "updated_at": row[9].isoformat() if row[9] else None,
        }

    async def _update_run(self, run_id: uuid.UUID, **fields: object) -> None:
        sets = ", ".join(f"{k} = :{k}" for k in fields)
        sets += ", updated_at = :now"
        fields["now"] = datetime.now(timezone.utc)
        fields["run_id"] = run_id
        await self.db.execute(
            text(f"UPDATE pipeline_runs SET {sets} WHERE id = :run_id"),
            fields,
        )
        await self.db.commit()

    async def _update_step(
        self,
        run_id: uuid.UUID,
        step: str,
        steps_completed: list[str],
    ) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text("""
                UPDATE pipeline_runs
                SET current_step = :step,
                    steps_completed = CAST(:steps AS jsonb),
                    status = 'running',
                    updated_at = :now
                WHERE id = :run_id
            """),
            {
                "step": step,
                "steps": json.dumps(steps_completed),
                "now": now,
                "run_id": run_id,
            },
        )
        await self.db.commit()

    async def _mark_completed(self, run_id: uuid.UUID, steps_completed: list[str]) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text("""
                UPDATE pipeline_runs
                SET status = 'completed',
                    current_step = NULL,
                    steps_completed = CAST(:steps AS jsonb),
                    completed_at = :now,
                    updated_at = :now
                WHERE id = :run_id
            """),
            {"steps": json.dumps(steps_completed), "now": now, "run_id": run_id},
        )
        await self.db.commit()

    async def _get_project_quotation_config(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict:
        result = await self.db.execute(
            text("""
                SELECT quotation_config
                FROM projects
                WHERE tenant_id = :tid AND id = :pid
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return {}
        return row[0]

    async def _notify_n8n_pipeline_callback(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        status: str,
        error_step: str | None = None,
        error_message: str | None = None,
    ) -> None:
        cfg = await self._get_project_quotation_config(tenant_id, project_id)
        callback_url = cfg.get("callback_url") or settings.N8N_PIPELINE_CALLBACK_URL
        if not callback_url:
            return

        source_platform = cfg.get("source_platform")
        platform_reply_info = cfg.get("platform_reply_info")

        # Resolve tenant slug for the callback
        slug_row = await self.db.execute(
            text("SELECT slug FROM tenants WHERE id = :tid"),
            {"tid": tenant_id},
        )
        tenant_slug = (slug_row.scalar() or "")

        payload: dict[str, object] = {
            "run_id": str(run_id),
            "tenant_id": str(tenant_id),
            "tenant_slug": tenant_slug,
            "project_id": str(project_id),
            "status": status,
            "source_platform": source_platform,
            "platform_reply_info": platform_reply_info,
            "error_step": error_step,
            "error_message": error_message,
        }

        if status == "completed":
            quotation_service = QuotationService(self.db)
            download = await quotation_service.get_download_url(
                tenant_id=tenant_id, project_id=project_id, fmt="docx"
            )
            if download:
                payload["download_url"] = download.url
                payload["file_name"] = download.file_name

        headers = {"Content-Type": "application/json"}
        if settings.N8N_PIPELINE_CALLBACK_TOKEN:
            headers["X-Callback-Token"] = settings.N8N_PIPELINE_CALLBACK_TOKEN

        try:
            timeout = httpx.Timeout(15.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                await client.post(
                    callback_url,
                    json=payload,
                    headers=headers,
                )
        except Exception as exc:
            logger.warning("N8N callback failed for pipeline %s: %s", run_id, exc)

    async def _mark_failed(
        self, run_id: uuid.UUID, step: str, message: str
    ) -> None:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            text("""
                UPDATE pipeline_runs
                SET status = 'failed',
                    error_step = :step,
                    error_message = :msg,
                    updated_at = :now
                WHERE id = :run_id
            """),
            {"step": step, "msg": message[:2000], "now": now, "run_id": run_id},
        )
        await self.db.commit()

    async def _rollback_step_work(self, run_id: uuid.UUID, step: str) -> None:
        try:
            await self.db.rollback()
        except Exception:
            logger.exception("Pipeline %s: rollback failed after step %s error", run_id, step)

    async def mark_stale_run_failed_if_needed(
        self,
        run: dict,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> dict:
        if run["status"] != "running":
            return run

        step = run.get("current_step") or "pipeline"
        timeout_seconds = STEP_TIMEOUT_SECONDS.get(step, 15 * 60)
        updated_at_raw = run.get("updated_at")
        if not updated_at_raw:
            return run

        updated_at = datetime.fromisoformat(updated_at_raw)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)

        stale_after = updated_at + timedelta(seconds=timeout_seconds)
        if datetime.now(timezone.utc) <= stale_after:
            return run

        message = (
            f"Pipeline appears stuck at {_step_label(step)}. No progress was recorded for "
            f"{timeout_seconds // 60} minutes. Please retry."
        )
        await self._mark_failed(uuid.UUID(run["id"]), step, message)
        await self._notify_n8n_pipeline_callback(
            run_id=uuid.UUID(run["id"]),
            tenant_id=tenant_id,
            project_id=project_id,
            status="failed",
            error_step=step,
            error_message=message,
        )
        run["status"] = "failed"
        run["error_step"] = step
        run["error_message"] = message
        return run

    # ------------------------------------------------------------------
    # Orchestrator — runs all steps in sequence
    # ------------------------------------------------------------------

    async def run_pipeline(
        self,
        run_id: uuid.UUID,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        resume_from: str | None = None,
    ) -> None:
        steps_to_run = list(STEPS)
        steps_completed: list[str] = []

        if resume_from:
            idx = STEPS.index(resume_from)
            steps_completed = STEPS[:idx]
            steps_to_run = STEPS[idx:]

        for step in steps_to_run:
            await self._update_step(run_id, step, steps_completed)
            logger.info("Pipeline %s: starting step %s", run_id, step)

            try:
                timeout = STEP_TIMEOUT_SECONDS[step]
                await asyncio.wait_for(
                    self._execute_step(step, tenant_id, project_id, user_id),
                    timeout=timeout,
                )
                steps_completed.append(step)
            except asyncio.TimeoutError:
                minutes = STEP_TIMEOUT_SECONDS[step] // 60
                message = f"{_step_label(step)} exceeded the {minutes} minute timeout. Please retry."
                logger.error("Pipeline %s: %s", run_id, message)
                await self._rollback_step_work(run_id, step)
                await self._mark_failed(run_id, step, message)
                await self._notify_n8n_pipeline_callback(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    status="failed",
                    error_step=step,
                    error_message=message,
                )
                return
            except Exception as exc:
                message = _error_message(exc)
                logger.error("Pipeline %s: step %s failed: %s", run_id, step, message, exc_info=True)
                await self._rollback_step_work(run_id, step)
                await self._mark_failed(run_id, step, message)
                await self._notify_n8n_pipeline_callback(
                    run_id=run_id,
                    tenant_id=tenant_id,
                    project_id=project_id,
                    status="failed",
                    error_step=step,
                    error_message=message,
                )
                return

        await self._mark_completed(run_id, steps_completed)
        await self._notify_n8n_pipeline_callback(
            run_id=run_id,
            tenant_id=tenant_id,
            project_id=project_id,
            status="completed",
        )
        logger.info("Pipeline %s completed successfully", run_id)

    async def _execute_step(
        self,
        step: str,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        if step == "boq_extraction":
            service = BoqExtractionService(self.db)
            await service.run(tenant_id, project_id)

        elif step == "spec_analysis":
            service = SpecAnalysisService(self.db)
            await service.run(tenant_id, project_id)

        elif step == "device_selection":
            service = DeviceSelectionService(self.db)
            await service.run(tenant_id, project_id)

        elif step == "panel_selection":
            service = PanelSelectionService(self.db)
            await service.run(tenant_id, project_id)

        elif step == "pricing":
            service = PricingService(self.db)
            await service.calculate(tenant_id, project_id)

        elif step == "quotation_generation":
            await self._run_quotation(tenant_id, project_id, user_id)

    async def _run_quotation(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        # Load quotation_config from project
        result = await self.db.execute(
            text("""
                SELECT quotation_config FROM projects
                WHERE id = :pid AND tenant_id = :tid
            """),
            {"pid": project_id, "tid": tenant_id},
        )
        row = result.fetchone()
        config = row[0] if row and row[0] else {}

        if not config:
            raise ValueError("Quotation config not saved on project. Cannot generate quotation.")

        data = GenerateQuotationRequest(
            client_name=config.get("client_name", ""),
            client_address=config.get("client_address", ""),
            subject=config.get("subject"),
            service_option=config.get("service_option", 1),
            margin_percent=config.get("margin_percent", 0.0),
            payment_terms_text=config.get("payment_terms_text"),
            inclusion_answers=config.get("inclusion_answers", {}),
        )

        service = QuotationService(self.db)
        await service.generate(tenant_id, project_id, user_id, data)

    # ------------------------------------------------------------------
    # Quotation config helpers
    # ------------------------------------------------------------------

    async def save_quotation_config(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        config: dict,
    ) -> dict:
        await self.db.execute(
            text("""
                UPDATE projects
                SET quotation_config = CAST(:config AS jsonb),
                    updated_at = :now
                WHERE id = :pid AND tenant_id = :tid
            """),
            {
                "config": json.dumps(config),
                "now": datetime.now(timezone.utc),
                "pid": project_id,
                "tid": tenant_id,
            },
        )
        await self.db.commit()
        return config

    async def get_quotation_config(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict | None:
        result = await self.db.execute(
            text("""
                SELECT quotation_config FROM projects
                WHERE id = :pid AND tenant_id = :tid
            """),
            {"pid": project_id, "tid": tenant_id},
        )
        row = result.fetchone()
        if not row or not row[0]:
            return None
        return row[0]

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    async def save_overrides(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        protocol: str | None,
        notification_type: str | None,
        network_type: str | None,
    ) -> dict:
        sets = []
        params: dict = {
            "pid": project_id,
            "tid": tenant_id,
            "now": datetime.now(timezone.utc),
        }

        if protocol is not None:
            sets.append("protocol = :protocol")
            params["protocol"] = protocol
        if notification_type is not None:
            sets.append("notification_type = :notification_type")
            params["notification_type"] = notification_type
        if network_type is not None:
            sets.append("network_type = :network_type")
            params["network_type"] = network_type

        if sets:
            sets.append("updated_at = :now")
            set_clause = ", ".join(sets)
            await self.db.execute(
                text(f"UPDATE projects SET {set_clause} WHERE id = :pid AND tenant_id = :tid"),
                params,
            )
            await self.db.commit()

        return {
            "protocol": protocol,
            "notification_type": notification_type,
            "network_type": network_type,
        }

    # ------------------------------------------------------------------
    # Document locking check
    # ------------------------------------------------------------------

    async def is_locked(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> bool:
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM pipeline_runs
                WHERE tenant_id = :tid AND project_id = :pid
                  AND status IN ('running', 'completed')
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        count = result.scalar() or 0
        return count > 0

    # ------------------------------------------------------------------
    # Validation before starting pipeline
    # ------------------------------------------------------------------

    async def validate_can_start(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> None:
        from fastapi import HTTPException, status

        # Check BOQ documents exist
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM documents
                WHERE tenant_id = :tid AND project_id = :pid AND type = 'BOQ'
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        boq_count = result.scalar() or 0
        if boq_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Upload a BOQ file before starting the pipeline.",
            )

        # Check quotation config is saved
        config = await self.get_quotation_config(tenant_id, project_id)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Configure quotation details before starting the pipeline.",
            )

        # Check no running pipeline exists
        result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM pipeline_runs
                WHERE tenant_id = :tid AND project_id = :pid
                  AND status = 'running'
            """),
            {"tid": tenant_id, "pid": project_id},
        )
        running = result.scalar() or 0
        if running > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pipeline is already running for this project.",
            )
