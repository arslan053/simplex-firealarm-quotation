"""Pydantic schemas for panel selection."""

from uuid import UUID

from pydantic import BaseModel


class JobStartResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    message: str


class GateResult(BaseModel):
    q1_total_devices: int
    q1_devices_per_panel: int
    q1_panel_count: int | None = None
    q1_passed: bool
    panel_type: str | None = None
    panel_label: str | None = None
    mx_addressable_blocked: bool = False
    q2_answer: str | None = None
    q2_passed: bool
    q3_answer: str | None = None
    q3_passed: bool
    is_4100es: bool = False
    entry_reasons: list[str] = []
    loop_count: int | None = None


class PanelProduct(BaseModel):
    product_code: str
    product_name: str | None = None
    quantity: int
    source: str
    question_no: int | None = None
    reason: str | None = None


class PanelGroupProduct(BaseModel):
    product_code: str
    product_name: str | None = None
    quantity: int
    source: str
    question_no: int | None = None
    reason: str | None = None


class PanelGroupResult(BaseModel):
    id: str
    boq_description: str | None = None
    loop_count: int
    quantity: int
    panel_type: str
    panel_label: str
    is_main: bool
    products: list[PanelGroupProduct]


class PanelSelectionResultsResponse(BaseModel):
    project_id: UUID
    panel_supported: bool
    gate_result: GateResult
    products: list[PanelProduct]
    is_multi_group: bool = False
    panel_groups: list[PanelGroupResult] = []
    status: str
    message: str


class PanelQuestionAnswer(BaseModel):
    question_no: int
    question: str
    answer: str
    confidence: str | None = None
    supporting_notes: list[str] = []


class PanelAnswersResponse(BaseModel):
    answers: list[PanelQuestionAnswer]
