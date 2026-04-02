from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings
from app.database import async_session_factory
from app.modules.tenants.repository import TenantRepository

SKIP_PATHS = {"/docs", "/redoc", "/openapi.json", "/api/health"}


class TenantResolverMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always skip CORS preflight requests — let CORSMiddleware handle them
        if request.method == "OPTIONS":
            request.state.tenant = None
            request.state.is_admin_domain = False
            return await call_next(request)

        path = request.url.path

        if path in SKIP_PATHS or path.startswith("/docs") or path.startswith("/redoc"):
            request.state.tenant = None
            request.state.is_admin_domain = False
            return await call_next(request)

        # 1) Check explicit tenant slug header (used when accessing via IP)
        explicit_slug = request.headers.get("x-tenant-slug", "").strip().lower()

        host = request.headers.get("x-tenant-host") or request.headers.get("host", "")
        hostname = host.split(":")[0].strip().lower()

        subdomain = hostname.split(".")[0] if hostname else ""

        # Use explicit slug if provided, otherwise fall back to subdomain
        slug = explicit_slug or subdomain

        if slug == settings.ADMIN_SUBDOMAIN:
            request.state.tenant = None
            request.state.is_admin_domain = True
            return await call_next(request)

        request.state.is_admin_domain = False

        # Bare IP or localhost with no explicit slug → admin domain
        if not explicit_slug and (not subdomain or subdomain in ("localhost", "127") or hostname == settings.APP_DOMAIN):
            request.state.tenant = None
            request.state.is_admin_domain = True
            return await call_next(request)

        async with async_session_factory() as db:
            repo = TenantRepository(db)
            tenant = await repo.get_by_slug(slug)

        if tenant and tenant.status == "suspended":
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant is suspended"},
            )

        if tenant:
            request.state.tenant = {
                "id": str(tenant.id),
                "slug": tenant.slug,
                "name": tenant.name,
                "status": tenant.status,
                "settings_json": tenant.settings_json,
            }
        else:
            request.state.tenant = None

        return await call_next(request)
