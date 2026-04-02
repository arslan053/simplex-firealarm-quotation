import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.modules.users.repository import UserRepository
from app.shared.email import get_email_sender
from app.shared.security import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
    hash_password,
    verify_password,
)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)

    async def authenticate(
        self,
        email: str,
        password: str,
        tenant_id: str | None = None,
        is_admin_domain: bool = False,
    ):
        user = await self.user_repo.get_by_email(email)

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        if not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
            )

        if is_admin_domain:
            if user.role != "super_admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only super_admin can log in on admin domain",
                )
        elif tenant_id:
            if str(user.tenant_id) != tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid email or password",
                )

        token = create_access_token(
            user_id=str(user.id),
            role=user.role,
            tenant_id=str(user.tenant_id) if user.tenant_id else None,
        )

        return user, token

    async def get_me(self, user_id: str):
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive"
            )
        return user

    async def change_password(self, user_id: str, current_password: str, new_password: str):
        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if not verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect"
            )

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        await self.db.flush()
        return user

    async def forgot_password(
        self,
        email: str,
        tenant_id: str | None = None,
        is_admin_domain: bool = False,
        tenant_slug: str | None = None,
    ):
        user = await self.user_repo.get_by_email(email)

        if not user or not user.is_active:
            return

        if is_admin_domain and user.role != "super_admin":
            return
        if tenant_id and str(user.tenant_id) != tenant_id:
            return

        reset_token = create_reset_token(str(user.id), user.password_hash)

        if is_admin_domain:
            host_prefix = settings.ADMIN_SUBDOMAIN
        elif tenant_slug:
            host_prefix = tenant_slug
        else:
            host_prefix = "app"

        reset_link = f"{settings.FRONTEND_URL.rstrip('/')}/auth/reset-password?token={reset_token}"
        if tenant_slug:
            base = f"http://{tenant_slug}.{settings.APP_DOMAIN}:5173"
            reset_link = f"{base}/auth/reset-password?token={reset_token}"
        elif is_admin_domain:
            base = f"http://{settings.ADMIN_SUBDOMAIN}.{settings.APP_DOMAIN}:5173"
            reset_link = f"{base}/auth/reset-password?token={reset_token}"

        email_sender = get_email_sender()
        await email_sender.send(
            to=email,
            subject="Password Reset Request",
            body=(
                f"<h2>Password Reset</h2>"
                f"<p>You requested a password reset. Click the link below:</p>"
                f"<p><a href='{reset_link}'>Reset Your Password</a></p>"
                f"<p>This link expires in 1 hour. If you didn't request this, ignore this email.</p>"
            ),
        )

    async def reset_password(self, token: str, new_password: str):
        try:
            payload = decode_reset_token(token)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid or expired reset token: {e}",
            )

        user_id = payload["sub"]
        ph_prefix = payload["ph"]

        user = await self.user_repo.get_by_id(uuid.UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reset token"
            )

        if user.password_hash[:8] != ph_prefix:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has already been used",
            )

        user.password_hash = hash_password(new_password)
        user.must_change_password = False
        await self.db.flush()
        return user
