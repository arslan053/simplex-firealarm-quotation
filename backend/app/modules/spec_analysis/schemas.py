from uuid import UUID

from pydantic import BaseModel


class SpecAnalysisResult(BaseModel):
    project_id: UUID
    status: str
    message: str
    spec_blocks_count: int
    answers_count: int

