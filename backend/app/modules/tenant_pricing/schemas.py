from __future__ import annotations

import math

from pydantic import BaseModel, Field, field_validator


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
    price: float = Field(ge=0, le=999_999_999)

    @field_validator("price")
    @classmethod
    def price_must_be_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Price must be a finite number")
        return round(v, 3)


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
