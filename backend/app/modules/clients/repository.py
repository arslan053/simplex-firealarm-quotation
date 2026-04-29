import uuid

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.projects.models import Project


class ClientRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: uuid.UUID,
        name: str,
        company_name: str,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
    ) -> Client:
        client = Client(
            tenant_id=tenant_id,
            name=name,
            company_name=company_name,
            email=email,
            phone=phone,
            address=address,
        )
        self.db.add(client)
        await self.db.flush()
        return client

    async def get_by_id_and_tenant(
        self, client_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Client | None:
        result = await self.db.execute(
            select(Client).where(
                and_(Client.id == client_id, Client.tenant_id == tenant_id)
            )
        )
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
    ) -> tuple[list[Client], int]:
        base = Client.tenant_id == tenant_id
        if search:
            search_term = f"%{search}%"
            base = and_(
                base,
                or_(
                    Client.name.ilike(search_term),
                    Client.company_name.ilike(search_term),
                    Client.email.ilike(search_term),
                ),
            )

        count_result = await self.db.execute(
            select(func.count()).select_from(Client).where(base)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * limit
        result = await self.db.execute(
            select(Client)
            .where(base)
            .order_by(Client.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def search_by_tenant(
        self,
        tenant_id: uuid.UUID,
        q: str,
    ) -> list[Client]:
        search_term = f"%{q}%"
        result = await self.db.execute(
            select(Client)
            .where(
                and_(
                    Client.tenant_id == tenant_id,
                    or_(
                        Client.name.ilike(search_term),
                        Client.company_name.ilike(search_term),
                    ),
                )
            )
            .order_by(Client.company_name)
            .limit(20)
        )
        return list(result.scalars().all())

    async def find_by_company_name(
        self,
        tenant_id: uuid.UUID,
        company_name: str,
    ) -> Client | None:
        result = await self.db.execute(
            select(Client).where(
                and_(Client.tenant_id == tenant_id, Client.company_name == company_name)
            )
        )
        return result.scalar_one_or_none()

    async def check_unique_company(
        self,
        tenant_id: uuid.UUID,
        company_name: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        """Return True if company_name is unique within the tenant."""
        conditions = and_(
            Client.tenant_id == tenant_id,
            Client.company_name == company_name,
        )
        if exclude_id:
            conditions = and_(conditions, Client.id != exclude_id)
        result = await self.db.execute(
            select(func.count()).select_from(Client).where(conditions)
        )
        return result.scalar_one() == 0

    async def update(self, client: Client, **kwargs) -> Client:
        for key, value in kwargs.items():
            setattr(client, key, value)
        await self.db.flush()
        return client

    async def list_projects_for_client(
        self,
        client_id: uuid.UUID,
        tenant_id: uuid.UUID,
        owner_user_id: uuid.UUID | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> tuple[list[Project], int]:
        base = and_(
            Project.client_id == client_id,
            Project.tenant_id == tenant_id,
        )
        if owner_user_id:
            base = and_(base, Project.owner_user_id == owner_user_id)

        count_result = await self.db.execute(
            select(func.count()).select_from(Project).where(base)
        )
        total = count_result.scalar_one()

        offset = (page - 1) * limit
        result = await self.db.execute(
            select(Project)
            .where(base)
            .order_by(Project.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total
