import json
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis.repository import AnalysisAnswerRepository
from app.modules.analysis.schemas import AnalysisAnswerResponse, AnalysisResultResponse
from app.modules.projects.models import Project
from app.modules.prompt_questions.models import PromptQuestion

logger = logging.getLogger(__name__)


class AnalysisService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.answer_repo = AnalysisAnswerRepository(db)

    async def get_results(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> AnalysisResultResponse:
        answers = await self.answer_repo.list_by_project(tenant_id, project_id)
        if not answers:
            return AnalysisResultResponse(
                project_id=project_id,
                answers=[],
                status="no_data",
                message="No analysis results found. Run analysis first.",
            )

        # Fetch questions for denormalization
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
                AnalysisAnswerResponse(
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

        # Read protocol from projects table
        proj_result = await self.db.execute(
            select(Project.protocol, Project.protocol_auto).where(
                Project.id == project_id,
                Project.tenant_id == tenant_id,
            )
        )
        proj_row = proj_result.first()
        final_protocol = proj_row.protocol if proj_row else None
        protocol_auto = proj_row.protocol_auto if proj_row else None

        return AnalysisResultResponse(
            project_id=project_id,
            answers=response_answers,
            status="success",
            message=f"{len(response_answers)} analysis results found.",
            final_protocol=final_protocol,
            protocol_auto=protocol_auto,
        )
