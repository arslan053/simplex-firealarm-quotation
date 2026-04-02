import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.repository import AuditRepository


class AuditService:
    def __init__(self, db: AsyncSession):
        self.repo = AuditRepository(db)

    async def log_action(
        self,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        tenant_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        metadata_json: dict | None = None,
    ):
        return await self.repo.create(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            metadata_json=metadata_json,
        )

    async def list_logs(
        self,
        tenant_id: uuid.UUID | None = None,
        skip: int = 0,
        limit: int = 50,
    ):
        return await self.repo.list_logs(tenant_id=tenant_id, skip=skip, limit=limit)
