import re

from pydantic import BaseModel, field_validator


# Strip control characters (keep printable + standard whitespace)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_MAX_NAME_LENGTH = 200
_MAX_PHONE_LENGTH = 50


class CompanySettingsResponse(BaseModel):
    letterhead_uploaded: bool
    letterhead_filename: str | None = None
    signature_uploaded: bool
    signature_filename: str | None = None
    signatory_name: str | None = None
    company_phone: str | None = None


class TextSettingsRequest(BaseModel):
    signatory_name: str | None = None
    company_phone: str | None = None

    @field_validator("signatory_name")
    @classmethod
    def clean_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = _CONTROL_CHARS.sub("", v)
        v = re.sub(r"\s+", " ", v).strip()
        return v[:_MAX_NAME_LENGTH] or None

    @field_validator("company_phone")
    @classmethod
    def clean_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = _CONTROL_CHARS.sub("", v)
        v = re.sub(r"\s+", " ", v).strip()
        return v[:_MAX_PHONE_LENGTH] or None
