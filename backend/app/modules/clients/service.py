import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.clients.repository import ClientRepository
from app.modules.clients.schemas import CreateClientRequest, UpdateClientRequest


class ClientService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ClientRepository(db)

    async def create_client(
        self,
        tenant_id: uuid.UUID,
        data: CreateClientRequest,
    ):
        is_unique = await self.repo.check_unique_company(tenant_id, data.company_name)
        if not is_unique:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A client with company name '{data.company_name}' already exists.",
            )

        return await self.repo.create(
            tenant_id=tenant_id,
            name=data.name,
            company_name=data.company_name,
            email=data.email,
            phone=data.phone,
            address=data.address,
        )

    async def get_client(
        self,
        client_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ):
        client = await self.repo.get_by_id_and_tenant(client_id, tenant_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
            )
        return client

    async def list_clients(
        self,
        tenant_id: uuid.UUID,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
    ):
        return await self.repo.list_by_tenant(
            tenant_id, page=page, limit=limit, search=search
        )

    async def search_clients(
        self,
        tenant_id: uuid.UUID,
        q: str,
    ):
        return await self.repo.search_by_tenant(tenant_id, q)

    async def update_client(
        self,
        client_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: UpdateClientRequest,
    ):
        client = await self.repo.get_by_id_and_tenant(client_id, tenant_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
            )

        update_fields = data.model_dump(exclude_unset=True)
        if not update_fields:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        if "company_name" in update_fields:
            is_unique = await self.repo.check_unique_company(
                tenant_id, update_fields["company_name"], exclude_id=client_id
            )
            if not is_unique:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"A client with company name '{update_fields['company_name']}' already exists.",
                )

        return await self.repo.update(client, **update_fields)

    async def list_client_projects(
        self,
        client_id: uuid.UUID,
        tenant_id: uuid.UUID,
        owner_user_id: uuid.UUID | None = None,
        page: int = 1,
        limit: int = 10,
    ):
        # Verify client exists in this tenant
        client = await self.repo.get_by_id_and_tenant(client_id, tenant_id)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Client not found"
            )

        return await self.repo.list_projects_for_client(
            client_id=client_id,
            tenant_id=tenant_id,
            owner_user_id=owner_user_id,
            page=page,
            limit=limit,
        )
