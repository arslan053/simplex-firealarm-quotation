import logging
import uuid
from io import BytesIO

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.images_handler import (
    build_and_upload_combined_pdf,
    read_image_files,
    validate_image_filenames,
)
from app.modules.boq.pdf_handler import (
    upload_pdf_to_minio,
    validate_pdf_filename,
)
from app.modules.boq.repository import BoqItemRepository, DocumentRepository
from app.modules.boq.schemas import (
    BoqItemListResponse,
    BoqItemResponse,
    DocumentResponse,
    build_pagination,
)
from app.shared.storage import upload_file
from app.shared.upload_security import (
    check_zip_bomb,
    sanitize_pdf,
    validate_file_size,
    validate_magic_bytes,
)

logger = logging.getLogger(__name__)

_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ALLOWED_EXCEL_EXTS = (".xlsx", ".xls")


def _convert_xls_to_xlsx(xls_bytes: bytes) -> bytes:
    """Convert legacy .xls bytes to .xlsx bytes using xlrd + openpyxl."""
    import xlrd
    from openpyxl import Workbook

    xls_book = xlrd.open_workbook(file_contents=xls_bytes)
    wb = Workbook()

    for idx, sheet_name in enumerate(xls_book.sheet_names()):
        xls_sheet = xls_book.sheet_by_index(idx)
        ws = wb.active if idx == 0 else wb.create_sheet()
        ws.title = sheet_name

        for row_idx in range(xls_sheet.nrows):
            for col_idx in range(xls_sheet.ncols):
                ws.cell(row=row_idx + 1, column=col_idx + 1,
                        value=xls_sheet.cell_value(row_idx, col_idx))

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


class BoqService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.doc_repo = DocumentRepository(db)
        self.item_repo = BoqItemRepository(db)

    # ------------------------------------------------------------------
    # Excel upload — store file only, no GPT extraction
    # ------------------------------------------------------------------

    async def upload_and_parse_boq(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
    ) -> DocumentResponse:
        filename = file.filename or "unknown.xlsx"
        if not filename.lower().endswith(_ALLOWED_EXCEL_EXTS):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .xlsx and .xls files are supported",
            )

        file_bytes = await file.read()
        validate_file_size(file_bytes)

        # Detect file type from extension for magic byte check
        ext = filename.rsplit(".", 1)[-1].lower()
        validate_magic_bytes(file_bytes, ext)

        # Convert legacy .xls → .xlsx so downstream parser (openpyxl) works
        if filename.lower().endswith(".xls") and not filename.lower().endswith(".xlsx"):
            logger.info("Converting .xls to .xlsx: %s", filename)
            file_bytes = _convert_xls_to_xlsx(file_bytes)
            filename = filename.rsplit(".", 1)[0] + ".xlsx"

        # ZIP bomb check on the final .xlsx bytes
        check_zip_bomb(file_bytes)

        file_size = len(file_bytes)

        file_uuid = uuid.uuid4()
        object_key = f"{tenant_id}/{project_id}/boq/{file_uuid}_{filename}"
        upload_file(
            object_key=object_key,
            data=file_bytes,
            content_type=_XLSX_MIME,
        )

        doc = await self.doc_repo.create(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=user_id,
            original_file_name=filename,
            file_size=file_size,
            object_key=object_key,
        )
        return DocumentResponse.model_validate(doc)

    # ------------------------------------------------------------------
    # PDF upload — store file only, no GPT extraction
    # ------------------------------------------------------------------

    async def upload_and_parse_boq_pdf(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        file: UploadFile,
    ) -> DocumentResponse:
        filename = file.filename or "unknown.pdf"
        validate_pdf_filename(filename)

        pdf_bytes = await file.read()
        validate_file_size(pdf_bytes)
        validate_magic_bytes(pdf_bytes, "pdf")
        pdf_bytes = sanitize_pdf(pdf_bytes)
        file_size = len(pdf_bytes)

        object_key = upload_pdf_to_minio(tenant_id, project_id, filename, pdf_bytes)

        doc = await self.doc_repo.create(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=user_id,
            original_file_name=filename,
            file_size=file_size,
            object_key=object_key,
        )
        return DocumentResponse.model_validate(doc)

    # ------------------------------------------------------------------
    # Images upload — combine into PDF and store, no GPT extraction
    # ------------------------------------------------------------------

    async def upload_and_parse_boq_images(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: uuid.UUID,
        files: list[UploadFile],
    ) -> DocumentResponse:
        validate_image_filenames(files)

        images = await read_image_files(files)

        object_key, pdf_bytes, filename = build_and_upload_combined_pdf(
            tenant_id, project_id, images,
        )
        file_size = len(pdf_bytes)

        doc = await self.doc_repo.create(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=user_id,
            original_file_name=filename,
            file_size=file_size,
            object_key=object_key,
        )
        return DocumentResponse.model_validate(doc)

    async def list_boq_items(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        page: int = 1,
        limit: int = 50,
    ) -> BoqItemListResponse:
        items, total = await self.item_repo.list_by_project(
            tenant_id, project_id, page=page, limit=limit
        )
        return BoqItemListResponse(
            data=[BoqItemResponse.model_validate(item) for item in items],
            pagination=build_pagination(page, limit, total),
        )

    async def toggle_boq_item_hidden(
        self,
        item_id: uuid.UUID,
        tenant_id: uuid.UUID,
        is_hidden: bool,
    ) -> BoqItemResponse:
        item = await self.item_repo.get_by_id_and_tenant(item_id, tenant_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BOQ item not found",
            )
        item = await self.item_repo.update_hidden(item, is_hidden)
        return BoqItemResponse.model_validate(item)

    async def list_documents(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[DocumentResponse]:
        docs = await self.doc_repo.get_by_project(tenant_id, project_id)
        return [DocumentResponse.model_validate(doc) for doc in docs]
