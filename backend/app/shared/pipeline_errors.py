import logging
from typing import Literal

import httpx
from fastapi import HTTPException, status
from minio.error import S3Error
from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    BadRequestError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

PipelineStep = Literal[
    "boq_extraction",
    "spec_analysis",
    "device_selection",
    "panel_selection",
    "pricing",
    "quotation_generation",
]

STEP_LABELS: dict[PipelineStep, str] = {
    "boq_extraction": "BOQ extraction",
    "spec_analysis": "specification analysis",
    "device_selection": "device selection",
    "panel_selection": "panel selection",
    "pricing": "pricing calculation",
    "quotation_generation": "quotation generation",
}


class PipelineUserError(HTTPException):
    """HTTPException whose detail is safe to show to project users."""

    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)


def no_ai_text_error(step: PipelineStep) -> PipelineUserError:
    if step == "boq_extraction":
        return PipelineUserError(
            "AI could not read the BOQ response. Please retry or upload a clearer BOQ file.",
            status.HTTP_502_BAD_GATEWAY,
        )
    if step == "spec_analysis":
        return PipelineUserError(
            "AI could not read the specification analysis response. Please retry.",
            status.HTTP_502_BAD_GATEWAY,
        )
    return PipelineUserError(
        f"AI could not read the {STEP_LABELS[step]} response. Please retry.",
        status.HTTP_502_BAD_GATEWAY,
    )


def invalid_ai_response_error(step: PipelineStep) -> PipelineUserError:
    if step == "boq_extraction":
        return PipelineUserError(
            "AI returned an invalid BOQ analysis response. Please retry or upload a clearer BOQ file.",
            status.HTTP_502_BAD_GATEWAY,
        )
    if step == "spec_analysis":
        return PipelineUserError(
            "AI returned an invalid specification analysis response. Please retry.",
            status.HTTP_502_BAD_GATEWAY,
        )
    return PipelineUserError(
        f"AI returned an invalid {STEP_LABELS[step]} response. Please retry.",
        status.HTTP_502_BAD_GATEWAY,
    )


def incomplete_ai_response_error(step: PipelineStep) -> PipelineUserError:
    if step == "boq_extraction":
        return PipelineUserError(
            "AI could not find valid BOQ items in the uploaded file. Please upload a BOQ document with clear item descriptions and quantities.",
            status.HTTP_502_BAD_GATEWAY,
        )
    if step == "spec_analysis":
        return PipelineUserError(
            "AI returned an incomplete specification analysis. Please retry.",
            status.HTTP_502_BAD_GATEWAY,
        )
    return PipelineUserError(
        f"AI returned an incomplete {STEP_LABELS[step]} response. Please retry.",
        status.HTTP_502_BAD_GATEWAY,
    )


def empty_boq_output_error() -> PipelineUserError:
    return PipelineUserError(
        "No BOQ items were found in the uploaded file. Please upload a valid BOQ document with clear item descriptions and quantities.",
        status.HTTP_400_BAD_REQUEST,
    )


def storage_read_error(step: PipelineStep, exc: Exception) -> PipelineUserError:
    logger.warning("%s: storage read failed: %s", step, exc)
    if step == "boq_extraction":
        return PipelineUserError(
            "The uploaded BOQ file could not be read. Please remove it and upload the BOQ again.",
            status.HTTP_400_BAD_REQUEST,
        )
    return PipelineUserError(
        "The uploaded specification file could not be read. Please remove it and upload the spec again.",
        status.HTTP_400_BAD_REQUEST,
    )


def storage_write_error(step: PipelineStep, exc: Exception) -> PipelineUserError:
    logger.exception("%s: storage write failed", step)
    return PipelineUserError(
        f"{STEP_LABELS[step].capitalize()} output could not be uploaded. Please retry.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def save_output_error(step: PipelineStep, exc: Exception) -> PipelineUserError:
    logger.exception("%s: output save failed", step)
    if step == "boq_extraction":
        return PipelineUserError(
            "BOQ items were extracted but could not be saved. Please retry.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return PipelineUserError(
        f"{STEP_LABELS[step].capitalize()} output could not be saved. Please retry.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def empty_pricing_output_error() -> PipelineUserError:
    return PipelineUserError(
        "Pricing could not be calculated because no selected products were found. Please retry panel selection.",
        status.HTTP_400_BAD_REQUEST,
    )


def document_generation_error(exc: Exception) -> PipelineUserError:
    logger.exception("quotation_generation: document generation failed")
    return PipelineUserError(
        "Quotation documents could not be generated. Please retry.",
        status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def normalize_openai_error(step: PipelineStep, exc: Exception) -> PipelineUserError:
    message = str(exc).lower()

    if _looks_like_context_limit(exc, message):
        if step == "boq_extraction":
            return PipelineUserError(
                "The uploaded document is too large for analysis. Please upload a smaller or clearer BOQ file.",
                status.HTTP_400_BAD_REQUEST,
            )
        if step == "spec_analysis":
            return PipelineUserError(
                "The BOQ/spec content is too large for analysis. Please upload a smaller spec file or simplify the BOQ.",
                status.HTTP_400_BAD_REQUEST,
            )
        return PipelineUserError(
            f"The project data is too large for {STEP_LABELS[step]}. Please reduce the uploaded content and retry.",
            status.HTTP_400_BAD_REQUEST,
        )

    if isinstance(exc, (APITimeoutError, httpx.TimeoutException)):
        return PipelineUserError(
            "AI analysis took too long. Please retry.",
            status.HTTP_504_GATEWAY_TIMEOUT,
        )

    if isinstance(exc, RateLimitError):
        return PipelineUserError(
            "AI service is busy right now. Please retry in a few minutes.",
            status.HTTP_429_TOO_MANY_REQUESTS,
        )

    if isinstance(exc, (APIConnectionError, APIError, httpx.HTTPError)):
        if step == "boq_extraction":
            detail = "AI service could not analyze the BOQ. Please retry."
        elif step == "spec_analysis":
            detail = "AI service could not complete specification analysis. Please retry."
        else:
            detail = f"AI service could not complete {STEP_LABELS[step]}. Please retry."
        return PipelineUserError(detail, status.HTTP_502_BAD_GATEWAY)

    raise exc


def _looks_like_context_limit(exc: Exception, message: str) -> bool:
    if isinstance(exc, BadRequestError) and (
        "context" in message
        or "token" in message
        or "maximum context" in message
        or "too many" in message
    ):
        return True
    return (
        "context_length" in message
        or "maximum context" in message
        or "context window" in message
        or "too many tokens" in message
        or "token limit" in message
    )


def is_storage_error(exc: Exception) -> bool:
    return isinstance(exc, (S3Error, OSError, IOError))
