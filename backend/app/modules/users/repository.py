import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_id_and_tenant(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> User | None:
        result = await self.db.execute(
            select(User).where(and_(User.id == user_id, User.tenant_id == tenant_id))
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> tuple[list[User], int]:
        count_result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(and_(User.tenant_id == tenant_id, User.is_active == True))
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            select(User)
            .where(and_(User.tenant_id == tenant_id, User.is_active == True))
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(
        self,
        email: str,
        password_hash: str,
        role: str,
        tenant_id: uuid.UUID | None = None,
        must_change_password: bool = False,
        name: str | None = None,
    ) -> User:
        user = User(
            email=email,
            name=name,
            password_hash=password_hash,
            role=role,
            tenant_id=tenant_id,
            must_change_password=must_change_password,
            is_active=True,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def count_active_admins(self, tenant_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(User)
            .where(
                and_(
                    User.tenant_id == tenant_id,
                    User.role == "admin",
                    User.is_active == True,
                )
            )
        )
        return result.scalar_one()

    async def count_by_tenants(self, tenant_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not tenant_ids:
            return {}
        result = await self.db.execute(
            select(User.tenant_id, func.count())
            .where(and_(User.tenant_id.in_(tenant_ids), User.is_active == True))
            .group_by(User.tenant_id)
        )
        return {row[0]: row[1] for row in result.all()}

    async def deactivate(self, user_id: uuid.UUID, tenant_id: uuid.UUID) -> User | None:
        user = await self.get_by_id_and_tenant(user_id, tenant_id)
        if not user:
            return None
        user.is_active = False
        user.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return user
