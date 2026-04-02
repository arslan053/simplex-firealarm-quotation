import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, get_tenant_db
from app.dependencies.auth import (
    UserContext,
    get_current_user,
    require_role,
    require_tenant_domain,
    require_tenant_match,
)
from app.modules.audit.service import AuditService
from app.modules.projects.countries import COUNTRIES
from app.modules.projects.schemas import (
    CreateProjectRequest,
    ProjectAdminListResponse,
    ProjectAdminResponse,
    ProjectListResponse,
    ProjectResponse,
    UpdateProjectRequest,
    build_pagination,
)
from app.modules.projects.service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/countries", response_model=list[str])
async def get_countries():
    """Return the list of valid countries."""
    return COUNTRIES


@router.post(
    "",
    response_model=ProjectResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def create_project(
    body: CreateProjectRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    if user.role == "super_admin":
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admins cannot create projects",
        )

    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ProjectService(db)
    project = await service.create_project(
        tenant_id=tenant_id,
        owner_user_id=uuid.UUID(user.id),
        data=body,
    )

    audit = AuditService(db)
    await audit.log_action(
        action="project.created",
        entity_type="project",
        entity_id=str(project.id),
        tenant_id=tenant_id,
        actor_user_id=uuid.UUID(user.id),
        metadata_json={
            "project_name": project.project_name,
            "client_name": project.client_name,
        },
    )

    return ProjectResponse.model_validate(project)


@router.get(
    "",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def list_projects(
    request: Request,
    user: UserContext = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    view: str = Query("all", pattern="^(all|my)$"),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    service = ProjectService(db)

    if user.role == "admin" and view == "my":
        # Admin viewing their own projects — full fields
        projects, total = await service.list_projects_for_owner(
            tenant_id, uuid.UUID(user.id), page=page, limit=limit, search=search
        )
        return ProjectListResponse(
            data=[ProjectResponse.model_validate(p) for p in projects],
            pagination=build_pagination(page, limit, total),
        )
    elif user.role == "admin":
        # Admin viewing all company projects — restricted fields
        projects, total = await service.list_projects_for_admin(
            tenant_id, page=page, limit=limit, search=search
        )
        items = []
        for p in projects:
            owner_email = p.owner.email if p.owner else None
            items.append(
                ProjectAdminResponse(
                    id=p.id,
                    project_name=p.project_name,
                    client_name=p.client_name,
                    status=p.status,
                    created_at=p.created_at,
                    created_by_name=owner_email,
                )
            )
        return ProjectAdminListResponse(
            data=items,
            pagination=build_pagination(page, limit, total),
        )
    else:
        # Employee — own projects only, full fields
        projects, total = await service.list_projects_for_owner(
            tenant_id, uuid.UUID(user.id), page=page, limit=limit, search=search
        )
        return ProjectListResponse(
            data=[ProjectResponse.model_validate(p) for p in projects],
            pagination=build_pagination(page, limit, total),
        )


@router.get(
    "/{project_id}",
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def get_project(
    project_id: uuid.UUID,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])
    service = ProjectService(db)

    if user.role == "admin":
        project = await service.get_project(project_id, tenant_id)
        # If admin is the owner, return full view (editable)
        if str(project.owner_user_id) == user.id:
            return ProjectResponse.model_validate(project)
        # Otherwise, return restricted view
        owner_email = project.owner.email if project.owner else None
        return ProjectAdminResponse(
            id=project.id,
            project_name=project.project_name,
            client_name=project.client_name,
            status=project.status,
            created_at=project.created_at,
            created_by_name=owner_email,
        )
    else:
        project = await service.get_own_project(
            project_id, uuid.UUID(user.id), tenant_id
        )
        return ProjectResponse.model_validate(project)


@router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    dependencies=[
        Depends(require_tenant_domain),
        Depends(require_tenant_match),
        require_role("admin", "employee"),
    ],
)
async def update_project(
    project_id: uuid.UUID,
    body: UpdateProjectRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_tenant_db),
):
    tenant = request.state.tenant
    tenant_id = uuid.UUID(tenant["id"])

    service = ProjectService(db)
    project = await service.update_project(
        project_id=project_id,
        owner_user_id=uuid.UUID(user.id),
        tenant_id=tenant_id,
        data=body,
    )

    audit = AuditService(db)
    await audit.log_action(
        action="project.updated",
        entity_type="project",
        entity_id=str(project.id),
        tenant_id=tenant_id,
        actor_user_id=uuid.UUID(user.id),
        metadata_json=body.model_dump(exclude_unset=True),
    )

    return ProjectResponse.model_validate(project)
