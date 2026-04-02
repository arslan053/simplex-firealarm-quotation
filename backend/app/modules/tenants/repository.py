import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants.models import Tenant


class TenantRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slug(self, slug: str) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        return result.scalar_one_or_none()

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant | None:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        return result.scalar_one_or_none()

    async def list_all(self, skip: int = 0, limit: int = 50) -> tuple[list[Tenant], int]:
        count_result = await self.db.execute(select(func.count()).select_from(Tenant))
        total = count_result.scalar_one()
        result = await self.db.execute(
            select(Tenant).order_by(Tenant.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, name: str, slug: str, settings_json: dict | None = None) -> Tenant:
        tenant = Tenant(name=name, slug=slug, status="active", settings_json=settings_json)
        self.db.add(tenant)
        await self.db.flush()
        return tenant

    async def update(self, tenant_id: uuid.UUID, **kwargs) -> Tenant | None:
        tenant = await self.get_by_id(tenant_id)
        if not tenant:
            return None
        for key, value in kwargs.items():
            if value is not None:
                setattr(tenant, key, value)
        await self.db.flush()
        return tenant
