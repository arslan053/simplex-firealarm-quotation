from __future__ import annotations

from pydantic import BaseModel


class ProductDetail(BaseModel):
    code: str
    price_sar: float


class PricingItem(BaseModel):
    id: str
    section: str
    row_number: int
    description: str | None
    quantity: float
    unit_cost_sar: float
    total_sar: float
    product_details: list[ProductDetail]


class PricingResponse(BaseModel):
    project_id: str
    project_name: str
    calculated_at: str
    usd_to_sar_rate: float
    items: list[PricingItem]
    device_subtotal: float
    panel_subtotal: float
    subtotal: float
