from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status

from app.shared.security import decode_access_token


@dataclass
class UserContext:
    id: str
    role: str
    tenant_id: str | None


def get_current_user(request: Request) -> UserContext:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

    token = auth_header[7:]
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = UserContext(
        id=payload["sub"],
        role=payload["role"],
        tenant_id=payload.get("tenant_id"),
    )

    request.state.user = user
    return user


def require_auth(request: Request, user: UserContext = Depends(get_current_user)) -> UserContext:
    path = request.url.path
    allowed_paths = {"/api/auth/me", "/api/auth/change-password"}

    if getattr(user, "_must_change_password", False) and path not in allowed_paths:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Must change password before accessing other resources",
        )
    return user


def require_admin_domain(request: Request) -> None:
    if not getattr(request.state, "is_admin_domain", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin domain required")


def require_tenant_domain(request: Request) -> dict:
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant domain required")
    return tenant


def require_tenant_match(
    request: Request,
    user: UserContext = Depends(get_current_user),
) -> None:
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant domain required")
    if user.tenant_id != tenant["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token tenant does not match domain tenant",
        )


def require_role(*allowed_roles: str):
    def dependency(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not permitted. Required: {allowed_roles}",
            )
        return user

    return Depends(dependency)
