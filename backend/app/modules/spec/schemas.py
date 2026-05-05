from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class SpecDocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    type: str
    original_file_name: str
    file_size: int
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class SpecUploadResponse(BaseModel):
    document: SpecDocumentResponse
    message: str


class SpecExistingCheckResponse(BaseModel):
    exists: bool
    document: SpecDocumentResponse | None = None

