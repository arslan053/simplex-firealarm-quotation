from uuid import UUID

from pydantic import BaseModel


class BoqExtractionResult(BaseModel):
    project_id: UUID
    status: str
    message: str
    boq_items_count: int

