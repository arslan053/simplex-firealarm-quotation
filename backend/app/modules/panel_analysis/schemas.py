from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PanelAnalysisAnswerResponse(BaseModel):
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


class PanelResult(BaseModel):
    total_detection_devices: int
    panel_count: int | None
    devices_per_panel: int | None
    label: str


class PanelAnalysisResultResponse(BaseModel):
    project_id: UUID
    answers: list[PanelAnalysisAnswerResponse]
    status: str
    message: str
    panel_result: PanelResult | None = None
