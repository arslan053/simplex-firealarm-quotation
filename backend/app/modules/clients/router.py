import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.audit.service import AuditService
from app.modules.clients.schemas import (
    ClientListResponse,
    ClientResponse,
    ClientSearchItem,
    CreateClientRequest,
    UpdateClientRequest,
    build_pagination,
)
from app.modules.clients.service import ClientService
from app.modules.projects.schemas import (
    ProjectListResponse,
    ProjectResponse,
    build_pagination as build_project_pagination,
)

router = APIRouter(prefix="/api/clients", tags=["clients"])


@router.post(
    "",
    response_model=ClientResponse,
    status_code=201,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def create_client(
    body: CreateClientRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ClientService(db)
    client = await service.create_client(tenant_id=tenant_id, data=body)

    audit = AuditService(db)
    await audit.log_action(
        action="client.created",
        entity_type="client",
        entity_id=str(client.id),
        tenant_id=tenant_id,
        actor_user_id=uuid.UUID(user.id),
        metadata_json={
            "name": client.name,
            "company_name": client.company_name,
        },
    )

    return ClientResponse.model_validate(client)


@router.get(
    "",
    response_model=ClientListResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def list_clients(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ClientService(db)
    clients, total = await service.list_clients(
        tenant_id, page=page, limit=limit, search=search
    )

    return ClientListResponse(
        data=[ClientResponse.model_validate(c) for c in clients],
        pagination=build_pagination(page, limit, total),
    )


@router.get(
    "/search",
    response_model=list[ClientSearchItem],
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def search_clients(
    request: Request,
    q: str = Query("", max_length=200),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ClientService(db)
    clients = await service.search_clients(tenant_id, q)

    return [ClientSearchItem.model_validate(c) for c in clients]


@router.get(
    "/{client_id}",
    response_model=ClientResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_client(
    client_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ClientService(db)
    client = await service.get_client(client_id, tenant_id)

    return ClientResponse.model_validate(client)


@router.patch(
    "/{client_id}",
    response_model=ClientResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def update_client(
    client_id: uuid.UUID,
    body: UpdateClientRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ClientService(db)
    client = await service.update_client(
        client_id=client_id,
        tenant_id=tenant_id,
        data=body,
    )

    audit = AuditService(db)
    await audit.log_action(
        action="client.updated",
        entity_type="client",
        entity_id=str(client.id),
        tenant_id=tenant_id,
        actor_user_id=uuid.UUID(user.id),
        metadata_json=body.model_dump(exclude_unset=True),
    )

    return ClientResponse.model_validate(client)


@router.get(
    "/{client_id}/projects",
    response_model=ProjectListResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def list_client_projects(
    client_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    # Employees only see their own projects for this client
    owner_filter = uuid.UUID(user.id) if user.role == "employee" else None

    service = ClientService(db)
    projects, total = await service.list_client_projects(
        client_id=client_id,
        tenant_id=tenant_id,
        owner_user_id=owner_filter,
        page=page,
        limit=limit,
    )

    def _with_client_name(p):
        resp = ProjectResponse.model_validate(p)
        if p.client_id and p.client:
            resp.client_name = p.client.company_name
        return resp

    return ProjectListResponse(
        data=[_with_client_name(p) for p in projects],
        pagination=build_project_pagination(page, limit, total),
    )
