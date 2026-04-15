from pydantic import BaseModel


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
