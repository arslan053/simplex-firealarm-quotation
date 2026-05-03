from __future__ import annotations

from pydantic import BaseModel, field_validator


class StartPipelineResponse(BaseModel):
    pipeline_run_id: str
    status: str


class PipelineStatusResponse(BaseModel):
    id: str
    status: str
    current_step: str | None = None
    steps_completed: list[str] = []
    error_message: str | None = None
    error_step: str | None = None
    retry_count: int = 0
    started_at: str | None = None
    completed_at: str | None = None


class QuotationConfigRequest(BaseModel):
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

    @field_validator("client_name", "client_address")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Field must not be blank")
        return v.strip()


class QuotationConfigResponse(BaseModel):
    quotation_config: dict


class OverridesRequest(BaseModel):
    protocol: str | None = None
    notification_type: str | None = None
    network_type: str | None = None

    @field_validator("protocol")
    @classmethod
    def validate_protocol(cls, v: str | None) -> str | None:
        if v is not None and v not in ("MX", "IDNET"):
            raise ValueError("protocol must be MX or IDNET")
        return v

    @field_validator("notification_type")
    @classmethod
    def validate_notification_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("addressable", "non_addressable"):
            raise ValueError("notification_type must be addressable or non_addressable")
        return v

    @field_validator("network_type")
    @classmethod
    def validate_network_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("wired", "fiber", "IP"):
            raise ValueError("network_type must be wired, fiber, or IP")
        return v
