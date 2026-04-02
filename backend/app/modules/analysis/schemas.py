from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AnalysisAnswerResponse(BaseModel):
    id: UUID
    project_id: UUID
    question_id: UUID
    question_no: int
    question_text: str
    category: str
    answer: str
    confidence: str
    supporting_notes: list[str]
    inferred_from: str
    created_at: datetime | None = None


class AnalysisResultResponse(BaseModel):
    project_id: UUID
    answers: list[AnalysisAnswerResponse]
    status: str
    message: str
    final_protocol: str | None = None
    protocol_auto: str | None = None
