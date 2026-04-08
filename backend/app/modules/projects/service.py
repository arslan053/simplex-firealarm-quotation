import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.projects.countries import (
    is_valid_country,
    normalize_city,
    normalize_country,
)
from app.modules.clients.repository import ClientRepository
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import CreateProjectRequest, UpdateProjectRequest


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ProjectRepository(db)

    async def create_project(
        self,
        tenant_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        data: CreateProjectRequest,
    ):
        if not is_valid_country(data.country):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid country '{data.country}'. Must be from the supported countries list.",
            )

        # Validate client_id exists in tenant
        client_repo = ClientRepository(self.db)
        client = await client_repo.get_by_id_and_tenant(data.client_id, tenant_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Client not found in this tenant.",
            )

        project = await self.repo.create(
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            project_name=data.project_name,
            client_id=data.client_id,
            country=normalize_country(data.country),
            city=normalize_city(data.city),
            due_date=data.due_date,
        )
        return project

    async def get_project(
        self,
        project_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ):
        project = await self.repo.get_by_id_and_tenant(project_id, tenant_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
            )
        return project

    async def get_own_project(
        self,
        project_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ):
        project = await self.repo.get_by_id_owner_tenant(
            project_id, owner_user_id, tenant_id
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you are not the owner",
            )
        return project

    async def update_project(
        self,
        project_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: UpdateProjectRequest,
    ):
        project = await self.repo.get_by_id_owner_tenant(
            project_id, owner_user_id, tenant_id
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found or you are not the owner",
            )

        update_fields = data.model_dump(exclude_unset=True)
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        if "country" in update_fields:
            if not is_valid_country(update_fields["country"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid country '{update_fields['country']}'.",
                )
            update_fields["country"] = normalize_country(update_fields["country"])

        if "city" in update_fields:
            update_fields["city"] = normalize_city(update_fields["city"])

        if "client_id" in update_fields and update_fields["client_id"] is not None:
            client_repo = ClientRepository(self.db)
            client = await client_repo.get_by_id_and_tenant(
                update_fields["client_id"], tenant_id
            )
            if not client:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Client not found in this tenant.",
                )

        project = await self.repo.update(project, **update_fields)
        return project

    async def list_projects_for_owner(
        self,
        tenant_id: uuid.UUID,
        owner_user_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
    ):
        return await self.repo.list_by_owner(
            tenant_id, owner_user_id, page=page, limit=limit, search=search
        )

    async def list_projects_for_admin(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
    ):
        return await self.repo.list_by_tenant(
            tenant_id, page=page, limit=limit, search=search
        )
