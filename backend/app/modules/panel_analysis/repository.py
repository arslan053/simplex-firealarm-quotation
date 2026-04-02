import uuid

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analysis.models import AnalysisAnswer
from app.modules.prompt_questions.models import PromptQuestion


class PanelAnalysisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_create(self, answers: list[AnalysisAnswer]) -> list[AnalysisAnswer]:
        self.db.add_all(answers)
        await self.db.flush()
        return answers

    async def list_by_project(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[AnalysisAnswer]:
        """Return only Panel_selection answers for a project."""
        panel_q_ids = select(PromptQuestion.id).where(
            PromptQuestion.category == "Panel_selection"
        )
        result = await self.db.execute(
            select(AnalysisAnswer)
            .where(
                and_(
                    AnalysisAnswer.tenant_id == tenant_id,
                    AnalysisAnswer.project_id == project_id,
                    AnalysisAnswer.question_id.in_(panel_q_ids),
                )
            )
            .order_by(AnalysisAnswer.created_at.asc())
        )
        return list(result.scalars().all())

    async def delete_by_project(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> None:
        """Delete only Panel_selection answers for a project."""
        panel_q_ids = select(PromptQuestion.id).where(
            PromptQuestion.category == "Panel_selection"
        )
        await self.db.execute(
            delete(AnalysisAnswer).where(
                and_(
                    AnalysisAnswer.tenant_id == tenant_id,
                    AnalysisAnswer.project_id == project_id,
                    AnalysisAnswer.question_id.in_(panel_q_ids),
                )
            )
        )
        await self.db.flush()
