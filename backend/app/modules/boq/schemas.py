from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    type: str
    original_file_name: str
    file_size: int
    created_at: datetime | None = None
    document_category: str | None = None
    document_category_confidence: float | None = None

    model_config = {"from_attributes": True}


class DocumentViewUrlResponse(BaseModel):
    url: str

