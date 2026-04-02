from uuid import UUID

from pydantic import BaseModel


class SpecAnalysisResult(BaseModel):
    project_id: UUID
    status: str
    message: str
    spec_blocks_count: int
    answers_count: int


class JobStartResponse(BaseModel):
    job_id: str
    status: str  # "started"
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "pending" | "running" | "success" | "failed"
    message: str
    spec_blocks_count: int = 0
    answers_count: int = 0
