import json
import logging
import uuid

from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from app.modules.boq.models import BoqItem
from app.modules.panel_analysis.repository import PanelAnalysisRepository
from app.modules.panel_analysis.schemas import PanelAnalysisAnswerResponse, PanelAnalysisResultResponse, PanelResult
from app.modules.prompt_questions.models import PromptQuestion

logger = logging.getLogger(__name__)


class PanelAnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.answer_repo = PanelAnalysisRepository(db)

    async def get_results(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> PanelAnalysisResultResponse:
        answers = await self.answer_repo.list_by_project(tenant_id, project_id)
        if not answers:
            return PanelAnalysisResultResponse(
                project_id=project_id,
                answers=[],
                status="no_data",
                message="No panel analysis results found. Run panel analysis first.",
            )

        question_ids = [a.question_id for a in answers]
        result = await self.db.execute(
            select(PromptQuestion).where(PromptQuestion.id.in_(question_ids))
        )
        question_map = {q.id: q for q in result.scalars().all()}

        response_answers = []
        for a in answers:
            q = question_map.get(a.question_id)
            if not q:
                continue
            response_answers.append(
                PanelAnalysisAnswerResponse(
                    id=a.id,
                    project_id=a.project_id,
                    question_id=a.question_id,
                    question_no=q.question_no,
                    question_text=q.question,
                    category=q.category,
                    answer=a.answer,
                    confidence=a.confidence,
                    supporting_notes=json.loads(a.supporting_notes),
                    inferred_from=a.inferred_from,
                    created_at=a.created_at,
                )
            )

        response_answers.sort(key=lambda x: x.question_no)

        # Compute panel result from answers
        panel_result = await self._compute_panel_result(
            tenant_id, project_id, response_answers
        )

        return PanelAnalysisResultResponse(
            project_id=project_id,
            answers=response_answers,
            status="success",
            message=f"{len(response_answers)} panel analysis results found.",
            panel_result=panel_result,
        )

    async def _compute_panel_result(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        answers: list[PanelAnalysisAnswerResponse],
    ) -> PanelResult | None:
        yes_answers = [a for a in answers if a.answer == "Yes"]
        if not yes_answers:
            return None

        # Pick highest confidence; ties broken by lowest question_no
        confidence_rank = {"High": 0, "Medium": 1, "Low": 2}
        yes_answers.sort(
            key=lambda a: (confidence_rank.get(a.confidence, 3), a.question_no)
        )
        winner = yes_answers[0]

        # Sum BOQ quantities
        detection_qty = await self._sum_boq_qty(
            tenant_id, project_id, "detection_devices"
        )
        total_devices = int(detection_qty)

        if winner.question_no in (101, 102):
            panel_qty = await self._sum_boq_qty(tenant_id, project_id, "panel")
            panel_count = int(panel_qty) if panel_qty else None
            if panel_count and panel_count > 0:
                devices_per_panel = total_devices // panel_count
                label = (
                    f"{total_devices} detection devices / {panel_count} panels "
                    f"= {devices_per_panel} devices per panel"
                )
            else:
                devices_per_panel = None
                label = f"{total_devices} detection devices (no panels found in BOQ)"
            return PanelResult(
                total_detection_devices=total_devices,
                panel_count=panel_count,
                devices_per_panel=devices_per_panel,
                label=label,
            )
        else:
            # Q103 — detection devices only, no panel division
            label = f"{total_devices} detection devices (single panel / no panel split)"
            return PanelResult(
                total_detection_devices=total_devices,
                panel_count=None,
                devices_per_panel=None,
                label=label,
            )

    async def _sum_boq_qty(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        category: str,
    ) -> Decimal:
        result = await self.db.execute(
            select(func.coalesce(func.sum(BoqItem.quantity), 0)).where(
                and_(
                    BoqItem.tenant_id == tenant_id,
                    BoqItem.project_id == project_id,
                    BoqItem.category == category,
                    BoqItem.is_hidden == False,  # noqa: E712
                )
            )
        )
        return result.scalar_one()
