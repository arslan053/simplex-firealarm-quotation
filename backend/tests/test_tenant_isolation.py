import pytest
from httpx import AsyncClient

from tests.conftest import make_token


@pytest.mark.asyncio
async def test_acme_token_cannot_access_beta(client: AsyncClient, seeded_data):
    """Token for tenant acme cannot access beta domain endpoints."""
    token = make_token(seeded_data["acme_admin"])
    resp = await client.get(
        "/api/tenant/users",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "beta.local",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_non_super_admin_cannot_access_admin_endpoints(client: AsyncClient, seeded_data):
    """Non-super_admin cannot access admin domain endpoints."""
    token = make_token(seeded_data["acme_admin"])
    resp = await client.get(
        "/api/admin/tenants",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "admin.local",
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_super_admin_can_access_admin_endpoints(client: AsyncClient, seeded_data):
    """Super admin can access admin domain endpoints."""
    token = make_token(seeded_data["super_admin"])
    resp = await client.get(
        "/api/admin/tenants",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "admin.local",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_tenant_admin_can_deactivate_employee(client: AsyncClient, seeded_data):
    """Tenant admin can deactivate employee within same tenant."""
    token = make_token(seeded_data["acme_admin"])
    employee_id = str(seeded_data["acme_employee"].id)

    resp = await client.post(
        f"/api/tenant/users/{employee_id}/deactivate",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "acme.local",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_cannot_deactivate_last_active_admin(client: AsyncClient, seeded_data):
    """Cannot deactivate the last active admin in a tenant."""
    token = make_token(seeded_data["beta_admin"])
    admin_id = str(seeded_data["beta_admin"].id)

    # beta has only one admin, so deactivating should fail
    resp = await client.post(
        f"/api/tenant/users/{admin_id}/deactivate",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "beta.local",
        },
    )
    # Should be 400 because can't deactivate self (and also last admin)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_suspended_tenant_blocks_access(client: AsyncClient, seeded_data):
    """Suspended tenant blocks access."""
    resp = await client.get(
        "/api/tenants/resolve",
        headers={"x-tenant-host": "suspended.local"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_tenant_admin_cannot_deactivate_cross_tenant(client: AsyncClient, seeded_data):
    """Admin from acme cannot deactivate user in beta."""
    token = make_token(seeded_data["acme_admin"])
    beta_employee_id = str(seeded_data["beta_employee"].id)

    resp = await client.post(
        f"/api/tenant/users/{beta_employee_id}/deactivate",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "acme.local",
        },
    )
    # Should fail - user not found in acme tenant
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_employee_cannot_access_user_management(client: AsyncClient, seeded_data):
    """Employee cannot access admin user management endpoints."""
    token = make_token(seeded_data["acme_employee"])
    resp = await client.get(
        "/api/tenant/users",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "acme.local",
        },
    )
    assert resp.status_code == 403
