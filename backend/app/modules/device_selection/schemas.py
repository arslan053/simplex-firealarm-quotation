import math
from uuid import UUID

from pydantic import BaseModel


class DeviceSelectionResult(BaseModel):
    project_id: UUID
    status: str
    message: str
    matched_count: int


class DeviceSelectionItem(BaseModel):
    boq_item_id: UUID
    boq_description: str | None = None
    selectable_id: UUID | None = None
    selectable_category: str | None = None
    selection_type: str = "none"
    product_codes: list[str] = []
    selectable_description: str | None = None
    reason: str | None = None
    status: str = "finalized"


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class DeviceSelectionResultsResponse(BaseModel):
    project_id: UUID
    data: list[DeviceSelectionItem]
    pagination: PaginationMeta
    network_type: str | None = None
    network_type_auto: str | None = None
    notification_type: str | None = None
    notification_type_auto: str | None = None


def build_pagination(page: int, limit: int, total: int) -> PaginationMeta:
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=math.ceil(total / limit) if limit > 0 else 0,
    )
