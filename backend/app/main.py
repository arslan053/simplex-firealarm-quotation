import defusedxml
defusedxml.defuse_stdlib()  # Patch stdlib XML parsers — blocks XML entity expansion attacks

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.middleware.tenant import TenantResolverMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.tenants.router import admin_router, resolve_router
from app.modules.clients.router import router as clients_router
from app.modules.projects.router import router as projects_router
from app.modules.boq.router import router as boq_router
from app.modules.boq.documents_router import router as documents_router
from app.modules.spec.router import router as spec_router
from app.modules.users.router import router as tenant_users_router
from app.modules.analysis.router import router as analysis_router
from app.modules.panel_analysis.router import router as panel_analysis_router
from app.modules.boq_extraction.router import router as boq_extraction_router
from app.modules.spec_analysis.router import router as spec_analysis_router
from app.modules.device_selection.router import router as device_selection_router
from app.modules.panel_selection.router import router as panel_selection_router
from app.modules.pricing.router import router as pricing_router
from app.modules.quotation.router import router as quotation_router
from app.modules.tenant_pricing.router import router as tenant_pricing_router
from app.modules.pipeline.router import router as pipeline_router
from app.modules.company_settings.router import router as company_settings_router
from app.modules.billing.router import router as billing_router
from app.modules.billing.webhook_router import webhook_router as billing_webhook_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Quotation Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

# TenantResolver runs first (added last), then CORS handles headers
_cors_kwargs: dict = {
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
if settings.cors_origins_list == ["*"]:
    _cors_kwargs["allow_origin_regex"] = r".*"
else:
    _cors_kwargs["allow_origins"] = settings.cors_origins_list
app.add_middleware(CORSMiddleware, **_cors_kwargs)

app.add_middleware(TenantResolverMiddleware)

app.include_router(auth_router)
app.include_router(resolve_router)
app.include_router(admin_router)
app.include_router(tenant_users_router)
app.include_router(clients_router)
app.include_router(projects_router)
app.include_router(boq_router)
app.include_router(documents_router)
app.include_router(spec_router)
app.include_router(analysis_router)
app.include_router(panel_analysis_router)
app.include_router(boq_extraction_router)
app.include_router(spec_analysis_router)
app.include_router(device_selection_router)
app.include_router(panel_selection_router)
app.include_router(pricing_router)
app.include_router(quotation_router)
app.include_router(tenant_pricing_router)
app.include_router(pipeline_router)
app.include_router(company_settings_router)
app.include_router(billing_router)
app.include_router(billing_webhook_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
