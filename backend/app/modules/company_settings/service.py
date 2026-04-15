from __future__ import annotations

import io
import json
import uuid
import zipfile

from docx import Document
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.storage import delete_file, get_file_bytes, upload_file
from app.shared.upload_security import (
    check_zip_bomb,
    sanitize_filename,
    validate_and_clean_image,
    validate_file_size,
    validate_magic_bytes,
)

from .schemas import CompanySettingsResponse


_MAX_LETTERHEAD_SIZE = 5 * 1024 * 1024  # 5MB
_MAX_SIGNATURE_SIZE = 2 * 1024 * 1024  # 2MB


class CompanySettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_settings_dict(self, tenant_id: uuid.UUID) -> dict:
        result = await self.db.execute(
            text("SELECT settings FROM tenant_settings WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        row = result.scalar()
        return row or {}

    def _build_response(self, settings: dict) -> CompanySettingsResponse:
        letterhead_key = settings.get("letterhead_key")
        signature_key = settings.get("signature_key")

        return CompanySettingsResponse(
            letterhead_uploaded=bool(letterhead_key),
            letterhead_filename=letterhead_key.rsplit("/", 1)[-1] if letterhead_key else None,
            signature_uploaded=bool(signature_key),
            signature_filename=signature_key.rsplit("/", 1)[-1] if signature_key else None,
            signatory_name=settings.get("signatory_name"),
            company_phone=settings.get("company_phone"),
        )

    async def get_settings(self, tenant_id: uuid.UUID) -> CompanySettingsResponse:
        settings = await self._get_settings_dict(tenant_id)
        return self._build_response(settings)

    async def update_text_settings(
        self,
        tenant_id: uuid.UUID,
        signatory_name: str | None,
        company_phone: str | None,
    ) -> CompanySettingsResponse:
        patch = {}
        if signatory_name is not None:
            patch["signatory_name"] = signatory_name
        if company_phone is not None:
            patch["company_phone"] = company_phone

        patch_json = json.dumps(patch)

        await self.db.execute(
            text("""
                INSERT INTO tenant_settings (tenant_id, settings)
                VALUES (:tid, CAST(:patch AS jsonb))
                ON CONFLICT (tenant_id)
                DO UPDATE SET
                    settings = tenant_settings.settings || CAST(:patch AS jsonb),
                    updated_at = now()
            """),
            {"tid": tenant_id, "patch": patch_json},
        )
        await self.db.commit()

        settings = await self._get_settings_dict(tenant_id)
        return self._build_response(settings)

    async def upload_letterhead(
        self,
        tenant_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
    ) -> CompanySettingsResponse:
        filename = sanitize_filename(filename)

        if not filename.lower().endswith(".docx"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .docx files are accepted for letterhead.",
            )

        validate_file_size(file_bytes, max_bytes=_MAX_LETTERHEAD_SIZE)
        validate_magic_bytes(file_bytes, "docx")
        check_zip_bomb(file_bytes)

        # Reject macro-enabled documents (.docm renamed to .docx)
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            names = [n.lower() for n in zf.namelist()]
            if "word/vbaproject.bin" in names:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Macro-enabled documents are not allowed. Please upload a standard .docx file.",
                )

        try:
            Document(io.BytesIO(file_bytes))
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file is not a valid Word document (.docx).",
            )

        # Delete old letterhead from MinIO if exists
        settings = await self._get_settings_dict(tenant_id)
        old_key = settings.get("letterhead_key")
        if old_key:
            try:
                delete_file(old_key)
            except Exception:
                pass

        # Upload to MinIO
        object_key = f"settings/{tenant_id}/letterhead.docx"
        upload_file(
            object_key,
            file_bytes,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        # Upsert settings
        patch = json.dumps({"letterhead_key": object_key})
        await self.db.execute(
            text("""
                INSERT INTO tenant_settings (tenant_id, settings)
                VALUES (:tid, CAST(:patch AS jsonb))
                ON CONFLICT (tenant_id)
                DO UPDATE SET
                    settings = tenant_settings.settings || CAST(:patch AS jsonb),
                    updated_at = now()
            """),
            {"tid": tenant_id, "patch": patch},
        )
        await self.db.commit()

        settings = await self._get_settings_dict(tenant_id)
        return self._build_response(settings)

    async def upload_signature(
        self,
        tenant_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
    ) -> CompanySettingsResponse:
        filename = sanitize_filename(filename)
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in ("png", "jpg", "jpeg"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PNG and JPG/JPEG images are accepted for signature.",
            )

        validate_file_size(file_bytes, max_bytes=_MAX_SIGNATURE_SIZE)
        validate_magic_bytes(file_bytes, ext)
        file_bytes = validate_and_clean_image(file_bytes)

        # Normalize ext for storage path
        ext = "png" if ext == "png" else "jpg"

        # Delete old signature from MinIO if exists
        settings = await self._get_settings_dict(tenant_id)
        old_key = settings.get("signature_key")
        if old_key:
            try:
                delete_file(old_key)
            except Exception:
                pass

        # Upload to MinIO
        object_key = f"settings/{tenant_id}/signature.{ext}"
        content_type = "image/png" if ext == "png" else "image/jpeg"
        upload_file(object_key, file_bytes, content_type=content_type)

        # Upsert settings
        patch = json.dumps({"signature_key": object_key})
        await self.db.execute(
            text("""
                INSERT INTO tenant_settings (tenant_id, settings)
                VALUES (:tid, CAST(:patch AS jsonb))
                ON CONFLICT (tenant_id)
                DO UPDATE SET
                    settings = tenant_settings.settings || CAST(:patch AS jsonb),
                    updated_at = now()
            """),
            {"tid": tenant_id, "patch": patch},
        )
        await self.db.commit()

        settings = await self._get_settings_dict(tenant_id)
        return self._build_response(settings)

    async def delete_letterhead(self, tenant_id: uuid.UUID) -> CompanySettingsResponse:
        settings = await self._get_settings_dict(tenant_id)
        key = settings.get("letterhead_key")
        if key:
            try:
                delete_file(key)
            except Exception:
                pass

        await self.db.execute(
            text("""
                UPDATE tenant_settings
                SET settings = settings - 'letterhead_key', updated_at = now()
                WHERE tenant_id = :tid
            """),
            {"tid": tenant_id},
        )
        await self.db.commit()

        settings = await self._get_settings_dict(tenant_id)
        return self._build_response(settings)

    async def delete_signature(self, tenant_id: uuid.UUID) -> CompanySettingsResponse:
        settings = await self._get_settings_dict(tenant_id)
        key = settings.get("signature_key")
        if key:
            try:
                delete_file(key)
            except Exception:
                pass

        await self.db.execute(
            text("""
                UPDATE tenant_settings
                SET settings = settings - 'signature_key', updated_at = now()
                WHERE tenant_id = :tid
            """),
            {"tid": tenant_id},
        )
        await self.db.commit()

        settings = await self._get_settings_dict(tenant_id)
        return self._build_response(settings)
