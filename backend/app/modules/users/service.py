import secrets
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import InviteUserRequest, UpdateUserRequest
from app.shared.email import get_email_sender
from app.shared.security import hash_password


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def list_users(self, tenant_id: uuid.UUID, skip: int = 0, limit: int = 50):
        return await self.user_repo.list_by_tenant(tenant_id, skip=skip, limit=limit)

    async def invite_user(self, tenant_id: uuid.UUID, tenant_slug: str, data: InviteUserRequest):
        if data.role == "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot create super_admin users from tenant context",
            )

        existing = await self.user_repo.get_by_email(data.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )

        random_password = secrets.token_urlsafe(12)
        user = await self.user_repo.create(
            email=data.email,
            password_hash=hash_password(random_password),
            role=data.role,
            tenant_id=tenant_id,
            must_change_password=False,
        )

        tenant_url = f"{settings.APP_PROTOCOL}://{tenant_slug}.{settings.APP_DOMAIN}"

        email_sender = get_email_sender()
        await email_sender.send(
            to=data.email,
            subject="You've Been Invited - Your Account Credentials",
            body=(
                f"<h2>Welcome!</h2>"
                f"<p>You've been invited to join the platform. Here are your login credentials:</p>"
                f"<p><strong>Login URL:</strong> <a href='{tenant_url}'>{tenant_url}</a></p>"
                f"<p><strong>Email:</strong> {data.email}</p>"
                f"<p><strong>Password:</strong> {random_password}</p>"
                f"<br>"
                f"<p>Please change your password after logging in from your Profile page.</p>"
            ),
        )

        return user

    async def update_user_role(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, data: UpdateUserRequest
    ):
        if data.role == "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot set super_admin role",
            )

        user = await self.user_repo.get_by_id_and_tenant(user_id, tenant_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant"
            )

        user.role = data.role
        await self.db.flush()
        return user

    async def deactivate_user(
        self, user_id: uuid.UUID, tenant_id: uuid.UUID, actor_user_id: uuid.UUID
    ):
        if str(user_id) == str(actor_user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate yourself",
            )

        user = await self.user_repo.get_by_id_and_tenant(user_id, tenant_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant"
            )

        if user.role == "admin":
            admin_count = await self.user_repo.count_active_admins(tenant_id)
            if admin_count <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot deactivate the last active admin",
                )

        deactivated = await self.user_repo.deactivate(user_id, tenant_id)
        if not deactivated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found in this tenant"
            )
        return deactivated
