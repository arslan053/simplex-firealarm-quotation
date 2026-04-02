import math
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


class ChunkResult(BaseModel):
    chunk_index: int
    start_page: int
    end_page: int
    markdown: str


class SpecJobStatusResponse(BaseModel):
    job_id: str
    status: str
    total_pages: int
    processed_pages: int
    results: list[ChunkResult]
    error: str | None = None


class SpecCancelResponse(BaseModel):
    job_id: str
    status: str
    message: str


class SpecBlockResponse(BaseModel):
    id: UUID
    document_id: UUID
    page_no: int
    parent_id: UUID | None
    order_in_page: int
    style: str
    level: int | None
    list_kind: str | None
    content: str

    model_config = {"from_attributes": True}


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total: int
    total_pages: int


class SpecBlockListResponse(BaseModel):
    data: list[SpecBlockResponse]
    pagination: PaginationMeta


class RawChunkResponse(BaseModel):
    chunk_index: int
    start_page: int
    end_page: int
    markdown: str


def build_spec_pagination(page: int, limit: int, total: int) -> PaginationMeta:
    return PaginationMeta(
        page=page,
        limit=limit,
        total=total,
        total_pages=math.ceil(total / limit) if limit > 0 else 0,
    )
