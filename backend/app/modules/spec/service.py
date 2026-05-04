import logging
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.spec.repository import SpecBlockRepository, SpecDocumentRepository
from app.modules.spec.schemas import (
    SpecDocumentResponse,
    SpecExistingCheckResponse,
    SpecUploadResponse,
)
from app.shared.storage import delete_file, upload_file
from app.shared.upload_security import (
    sanitize_filename,
    sanitize_pdf,
    validate_file_size,
    validate_magic_bytes,
)

logger = logging.getLogger(__name__)


class SpecService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = SpecDocumentRepository(db)
        self.block_repo = SpecBlockRepository(db)

    async def check_existing(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> SpecExistingCheckResponse:
        doc = await self.repo.get_existing_spec(tenant_id, project_id)
        if doc:
            return SpecExistingCheckResponse(
                exists=True,
                document=SpecDocumentResponse.model_validate(doc),
            )
        return SpecExistingCheckResponse(exists=False)

    async def upload_and_start(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
    ) -> SpecUploadResponse:
        # Validate file extension
        raw_name = file.filename or "unknown.pdf"
        if not raw_name.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .pdf files are supported",
            )
        filename = sanitize_filename(raw_name)

        # Read file bytes and run security checks
        file_bytes = await file.read()
        validate_file_size(file_bytes)
        validate_magic_bytes(file_bytes, "pdf")
        file_bytes = sanitize_pdf(file_bytes)
        file_size = len(file_bytes)

        # Delete old spec if exists (blocks + document + MinIO file)
        old_doc = await self.repo.get_existing_spec(tenant_id, project_id)
        if old_doc:
            await self.block_repo.delete_by_document(old_doc.id, tenant_id)
            try:
                delete_file(old_doc.object_key)
            except Exception:
                logger.warning("Failed to delete old spec file from MinIO: %s", old_doc.object_key)
            await self.repo.delete(old_doc)

        # Upload to MinIO
        file_uuid = uuid.uuid4()
        object_key = f"{tenant_id}/{project_id}/spec/{file_uuid}_{filename}"
        upload_file(
            object_key=object_key,
            data=file_bytes,
            content_type="application/pdf",
        )

        # Create Document record
        doc = await self.repo.create(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=user_id,
            original_file_name=filename,
            file_size=file_size,
            object_key=object_key,
        )

        return SpecUploadResponse(
            document=SpecDocumentResponse.model_validate(doc),
            message="Specification uploaded. Run spec analysis to extract.",
        )
