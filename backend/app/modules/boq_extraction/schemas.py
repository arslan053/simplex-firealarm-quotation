from uuid import UUID

from pydantic import BaseModel


class BoqExtractionResult(BaseModel):
    project_id: UUID
    status: str
    message: str
    boq_items_count: int


class JobStartResponse(BaseModel):
    job_id: str
    status: str  # "started"
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str  # "pending" | "running" | "success" | "failed"
    message: str
    boq_items_count: int = 0
