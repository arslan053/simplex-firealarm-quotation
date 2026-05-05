import uuid

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.models import Document
from app.modules.spec.models import SpecBlock


class SpecDocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_existing_spec(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Document | None:
        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.tenant_id == tenant_id,
                    Document.project_id == project_id,
                    Document.type == "SPEC",
                )
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        original_file_name: str,
        file_size: int,
        object_key: str,
    ) -> Document:
        doc = Document(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=uploaded_by_user_id,
            type="SPEC",
            original_file_name=original_file_name,
            file_size=file_size,
            object_key=object_key,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def delete(self, doc: Document) -> None:
        await self.db.delete(doc)
        await self.db.flush()


class SpecBlockRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_create(self, blocks: list[SpecBlock]) -> list[SpecBlock]:
        self.db.add_all(blocks)
        await self.db.flush()
        return blocks

    async def delete_by_document(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        await self.db.execute(
            delete(SpecBlock).where(
                and_(
                    SpecBlock.document_id == document_id,
                    SpecBlock.tenant_id == tenant_id,
                )
            )
        )
        await self.db.flush()
