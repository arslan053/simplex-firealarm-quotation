from __future__ import annotations

from pydantic import BaseModel, field_validator


class GenerateQuotationRequest(BaseModel):
    client_name: str
    client_address: str
    service_option: int = 1
    advance_percent: float = 25.0
    delivery_percent: float = 70.0
    completion_percent: float = 5.0
    margin_percent: float = 0.0

    @field_validator("service_option")
    @classmethod
    def validate_service_option(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("service_option must be 1, 2, or 3")
        return v

    @field_validator("completion_percent")
    @classmethod
    def validate_percentages_sum(cls, v: float, info) -> float:
        advance = info.data.get("advance_percent", 25.0)
        delivery = info.data.get("delivery_percent", 70.0)
        total = advance + delivery + v
        if abs(total - 100.0) > 0.01:
            raise ValueError(
                f"Payment percentages must sum to 100 (got {total})"
            )
        return v


class QuotationResponse(BaseModel):
    id: str
    project_id: str
    reference_number: str
    client_name: str
    client_address: str
    service_option: int
    advance_percent: float
    delivery_percent: float
    completion_percent: float
    margin_percent: float
    subtotal_sar: float
    vat_sar: float
    grand_total_sar: float
    original_file_name: str
    created_at: str
    updated_at: str


class QuotationDownloadResponse(BaseModel):
    url: str
    file_name: str
