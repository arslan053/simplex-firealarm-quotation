import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.tenants.models import Tenant
from app.modules.tenants.repository import TenantRepository
from app.modules.tenants.schemas import TenantCreate, TenantUpdate
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.shared.email import get_email_sender
from app.shared.security import hash_password


class TenantService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tenant_repo = TenantRepository(db)
        self.user_repo = UserRepository(db)

    async def list_tenants(self, skip: int = 0, limit: int = 50):
        return await self.tenant_repo.list_all(skip=skip, limit=limit)

    async def get_tenant(self, tenant_id: uuid.UUID):
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant

    async def create_tenant(self, data: TenantCreate):
        existing = await self.tenant_repo.get_by_slug(data.slug)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant with slug '{data.slug}' already exists",
            )

        existing_user = await self.user_repo.get_by_email(data.admin_email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email '{data.admin_email}' already exists",
            )

        tenant = await self.tenant_repo.create(name=data.name, slug=data.slug)

        random_password = secrets.token_urlsafe(12)
        admin_user = await self.user_repo.create(
            email=data.admin_email,
            password_hash=hash_password(random_password),
            role="admin",
            tenant_id=tenant.id,
            must_change_password=False,
        )

        tenant_url = f"{settings.APP_PROTOCOL}://{data.slug}.{settings.APP_DOMAIN}"

        email_sender = get_email_sender()
        await email_sender.send(
            to=data.admin_email,
            subject=f"Welcome to {tenant.name} - Your Admin Account",
            body=(
                f"<h2>Welcome to {tenant.name}</h2>"
                f"<p>Your admin account has been created. Here are your login credentials:</p>"
                f"<p><strong>Login URL:</strong> <a href='{tenant_url}'>{tenant_url}</a></p>"
                f"<p><strong>Email:</strong> {data.admin_email}</p>"
                f"<p><strong>Password:</strong> {random_password}</p>"
                f"<br>"
                f"<p>Please change your password after logging in from your Profile page.</p>"
            ),
        )

        return tenant, admin_user

    async def delete_tenant(self, tenant_id: uuid.UUID):
        tenant = await self.tenant_repo.get_by_id(tenant_id)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

        # Delete all related data in correct order (foreign key deps)
        for table in [
            "boq_device_selections",
            "analysis_answers",
            "spec_blocks",
            "boq_items",
            "documents",
            "projects",
            "audit_logs",
            "users",
        ]:
            await self.db.execute(text(f"DELETE FROM {table} WHERE tenant_id = :tid"), {"tid": tenant_id})

        # Delete the tenant itself
        await self.db.execute(delete(Tenant).where(Tenant.id == tenant_id))
        await self.db.commit()

    async def update_tenant(self, tenant_id: uuid.UUID, data: TenantUpdate):
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update"
            )

        tenant = await self.tenant_repo.update(tenant_id, **update_data)
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant
