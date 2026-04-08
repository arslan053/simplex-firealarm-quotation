import uuid
from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.models import Client
from app.modules.projects.models import Project


class ProjectRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        project_name: str,
        client_id: uuid.UUID,
        country: str,
        city: str,
        due_date: date,
    ) -> Project:
        project = Project(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            project_name=project_name,
            client_id=client_id,
            country=country,
            city=city,
            due_date=due_date,
            status="IN_PROGRESS",
            panel_family=None,
        )
        self.db.add(project)
        await self.db.flush()
        return project

    async def get_by_id_and_tenant(
        self, project_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Project | None:
        result = await self.db.execute(
            select(Project).where(
                and_(Project.id == project_id, Project.tenant_id == tenant_id)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_owner_tenant(
        self, project_id: uuid.UUID, owner_user_id: uuid.UUID, tenant_id: uuid.UUID
    ) -> Project | None:
        result = await self.db.execute(
            select(Project).where(
                and_(
                    Project.id == project_id,
                    Project.owner_user_id == owner_user_id,
                    Project.tenant_id == tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self,
        tenant_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
    ) -> tuple[list[Project], int]:
        base = and_(
            Project.tenant_id == tenant_id,
            Project.owner_user_id == owner_user_id,
        )
        join_needed = False
        if search:
            join_needed = True
            search_term = f"%{search}%"
            base = and_(
                base,
                or_(
                    Project.project_name.ilike(search_term),
                    Client.company_name.ilike(search_term),
                ),
            )

        count_q = select(func.count()).select_from(Project)
        if join_needed:
            count_q = count_q.outerjoin(Client, Project.client_id == Client.id)
        count_result = await self.db.execute(count_q.where(base))
        total = count_result.scalar_one()

        offset = (page - 1) * limit
        q = select(Project)
        if join_needed:
            q = q.outerjoin(Client, Project.client_id == Client.id)
        result = await self.db.execute(
            q.where(base)
            .order_by(Project.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_by_tenant(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
    ) -> tuple[list[Project], int]:
        base = Project.tenant_id == tenant_id
        join_needed = False
        if search:
            join_needed = True
            search_term = f"%{search}%"
            base = and_(
                base,
                or_(
                    Project.project_name.ilike(search_term),
                    Client.company_name.ilike(search_term),
                ),
            )

        count_q = select(func.count()).select_from(Project)
        if join_needed:
            count_q = count_q.outerjoin(Client, Project.client_id == Client.id)
        count_result = await self.db.execute(count_q.where(base))
        total = count_result.scalar_one()

        offset = (page - 1) * limit
        q = select(Project)
        if join_needed:
            q = q.outerjoin(Client, Project.client_id == Client.id)
        result = await self.db.execute(
            q.where(base)
            .order_by(Project.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def update(self, project: Project, **kwargs) -> Project:
        for key, value in kwargs.items():
            if value is not None:
                setattr(project, key, value)
        await self.db.flush()
        return project
