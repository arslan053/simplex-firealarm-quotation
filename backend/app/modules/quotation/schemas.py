from __future__ import annotations

from pydantic import BaseModel, field_validator


class GenerateQuotationRequest(BaseModel):
    client_name: str
    client_address: str
    subject: str | None = None
    service_option: int = 1
    margin_percent: float = 0.0
    payment_terms_text: str | None = None
    inclusion_answers: dict[str, bool] = {}

    @field_validator("service_option")
    @classmethod
    def validate_service_option(cls, v: int) -> int:
        if v not in (1, 2, 3):
            raise ValueError("service_option must be 1, 2, or 3")
        return v


class QuotationResponse(BaseModel):
    id: str
    project_id: str
    reference_number: str
    client_name: str
    client_address: str
    subject: str | None = None
    service_option: int
    margin_percent: float
    payment_terms_text: str | None = None
    inclusion_answers: dict[str, bool] = {}
    subtotal_sar: float
    vat_sar: float
    grand_total_sar: float
    original_file_name: str
    created_at: str
    updated_at: str


class InclusionQuestionItem(BaseModel):
    key: str
    text: str
    mode: str
    value: bool | None
    group: str | None


class InclusionQuestionsResponse(BaseModel):
    questions: list[InclusionQuestionItem]


class QuotationDownloadResponse(BaseModel):
    url: str
    file_name: str
