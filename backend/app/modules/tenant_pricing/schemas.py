from __future__ import annotations

from pydantic import BaseModel


class TenantProductPrice(BaseModel):
    product_id: str
    code: str
    description: str
    category: str
    price: float
    currency: str


class PriceListResponse(BaseModel):
    items: list[TenantProductPrice]
    total: int
    prices_set: int


class PriceUpdateItem(BaseModel):
    product_id: str
    price: float


class PriceUpdateRequest(BaseModel):
    items: list[PriceUpdateItem]


class PriceUpdateResponse(BaseModel):
    updated: int


class TemplateValidationError(BaseModel):
    row: int
    expected_code: str
    got_code: str
    message: str


class UploadResponse(BaseModel):
    updated: int
    errors: list[TemplateValidationError]
