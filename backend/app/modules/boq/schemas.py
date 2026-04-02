import math
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer


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


class DimensionEntry(BaseModel):
    name: str
    quantity: float | int | None = None
    building_count: float | int | None = None


class BoqItemResponse(BaseModel):
    id: UUID
    row_number: int
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    is_hidden: bool
    is_valid: bool
    type: str = "boq_item"
    category: str | None = None
    dimensions: list[DimensionEntry] | None = None

    model_config = {"from_attributes": True}

    @field_serializer("quantity")
    @classmethod
    def serialize_quantity(cls, v: Decimal | None) -> float | int | None:
        """Serialize quantity without unnecessary trailing zeros.

        8.0000 → 8, 8.5000 → 8.5, None → None
        """
        if v is None:
            return None
        # normalize() strips trailing zeros: Decimal('8.0000') → Decimal('8')
        normalized = v.normalize()
        # If it has no fractional part, return int
        if normalized == normalized.to_integral_value():
            return int(normalized)
        return float(normalized)


class BoqUploadResponse(BaseModel):
    document: DocumentResponse
    items: list[BoqItemResponse]
    total_items: int
    valid_count: int
    invalid_count: int
    status: str  # "success" | "partial"
    message: str


class BoqParseErrorResponse(BaseModel):
    status: str = "failed"
    missing_columns: list[str]
    message: str
    document: DocumentResponse | None = None


class ToggleHiddenRequest(BaseModel):
    is_hidden: bool


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class BoqItemListResponse(BaseModel):
    data: list[BoqItemResponse]
    pagination: PaginationMeta


class DocumentCategoryDetail(BaseModel):
    document_id: UUID
    category: str
    confidence: float


class LabelingResponse(BaseModel):
    project_id: UUID
    total_labeled: int
    document_categories: list[DocumentCategoryDetail]
    status: str
    message: str


def build_pagination(page: int, limit: int, total: int) -> PaginationMeta:
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=math.ceil(total / limit) if limit > 0 else 0,
    )
