import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        tenant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        metadata_json: dict | None = None,
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata_json,
        )
        self.db.add(log)
        await self.db.flush()
        return log

    async def list_logs(
        self,
        tenant_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if tenant_id:
            query = query.where(AuditLog.tenant_id == tenant_id)
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())
