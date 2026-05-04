import uuid

from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.boq.models import BoqItem, Document


class DocumentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
        uploaded_by_user_id: uuid.UUID,
        original_file_name: str,
        file_size: int,
        object_key: str,
        doc_type: str = "BOQ",
    ) -> Document:
        doc = Document(
            tenant_id=tenant_id,
            project_id=project_id,
            uploaded_by_user_id=uploaded_by_user_id,
            type=doc_type,
            original_file_name=original_file_name,
            file_size=file_size,
            object_key=object_key,
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def get_by_project(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(
                and_(
                    Document.tenant_id == tenant_id,
                    Document.project_id == project_id,
                    Document.type == "BOQ",
                )
            )
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_all_by_project(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[Document]:
        """Return ALL documents (BOQ + SPEC) for a project."""
        result = await self.db.execute(
            select(Document)
            .where(
                and_(
                    Document.tenant_id == tenant_id,
                    Document.project_id == project_id,
                )
            )
            .order_by(Document.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(
        self,
        doc_id: uuid.UUID,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> Document | None:
        result = await self.db.execute(
            select(Document).where(
                and_(
                    Document.id == doc_id,
                    Document.tenant_id == tenant_id,
                    Document.project_id == project_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, doc: Document) -> None:
        await self.db.delete(doc)
        await self.db.flush()

    async def update_document_category(
        self,
        doc_id: uuid.UUID,
        tenant_id: uuid.UUID,
        category: str,
        confidence: float,
    ) -> None:
        await self.db.execute(
            update(Document)
            .where(
                and_(Document.id == doc_id, Document.tenant_id == tenant_id)
            )
            .values(
                document_category=category,
                document_category_confidence=confidence,
            )
        )
        await self.db.flush()


class BoqItemRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def bulk_create(self, items: list[BoqItem]) -> list[BoqItem]:
        self.db.add_all(items)
        await self.db.flush()
        return items

    async def get_max_row_number(
        self, tenant_id: uuid.UUID, project_id: uuid.UUID
    ) -> int:
        """Return the highest row_number for a project, or 0 if none exist."""
        result = await self.db.execute(
            select(func.coalesce(func.max(BoqItem.row_number), 0)).where(
                and_(
                    BoqItem.tenant_id == tenant_id,
                    BoqItem.project_id == project_id,
                )
            )
        )
        return result.scalar_one()

    async def list_boq_type_items_by_project(
        self,
        tenant_id: uuid.UUID,
        project_id: uuid.UUID,
    ) -> list[BoqItem]:
        result = await self.db.execute(
            select(BoqItem)
            .where(
                and_(
                    BoqItem.tenant_id == tenant_id,
                    BoqItem.project_id == project_id,
                    BoqItem.type == "boq_item",
                )
            )
            .order_by(BoqItem.row_number.asc())
        )
        return list(result.scalars().all())

    async def bulk_update_categories(
        self,
        updates: dict[uuid.UUID, str],
        tenant_id: uuid.UUID,
    ) -> None:
        for item_id, category in updates.items():
            await self.db.execute(
                update(BoqItem)
                .where(
                    and_(BoqItem.id == item_id, BoqItem.tenant_id == tenant_id)
                )
                .values(category=category)
            )
        await self.db.flush()

    async def delete_by_document_id(
        self, document_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> None:
        await self.db.execute(
            delete(BoqItem).where(
                and_(
                    BoqItem.document_id == document_id,
                    BoqItem.tenant_id == tenant_id,
                )
            )
        )
        await self.db.flush()
