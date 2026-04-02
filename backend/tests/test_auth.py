import pytest
from httpx import AsyncClient

from tests.conftest import make_token


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seeded_data):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@acme-test.com", "password": "password123"},
        headers={"x-tenant-host": "acme.local"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@acme-test.com"
    assert data["user"]["role"] == "admin"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, seeded_data):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@acme-test.com", "password": "wrongpassword"},
        headers={"x-tenant-host": "acme.local"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_wrong_tenant(client: AsyncClient, seeded_data):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@acme-test.com", "password": "password123"},
        headers={"x-tenant-host": "beta.local"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient, seeded_data):
    token = make_token(seeded_data["acme_admin"])
    resp = await client.get(
        "/api/auth/me",
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "acme.local",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "admin@acme-test.com"
    assert data["role"] == "admin"


@pytest.mark.asyncio
async def test_me_no_token(client: AsyncClient, seeded_data):
    resp = await client.get(
        "/api/auth/me",
        headers={"x-tenant-host": "acme.local"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, seeded_data):
    token = make_token(seeded_data["acme_employee"])
    resp = await client.post(
        "/api/auth/change-password",
        json={"current_password": "password123", "new_password": "newpassword123"},
        headers={
            "authorization": f"Bearer {token}",
            "x-tenant-host": "acme.local",
        },
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_forgot_password_returns_200(client: AsyncClient, seeded_data):
    resp = await client.post(
        "/api/auth/forgot-password",
        json={"email": "admin@acme-test.com"},
        headers={"x-tenant-host": "acme.local"},
    )
    assert resp.status_code == 200

    # Also returns 200 for non-existent email (no info leak)
    resp2 = await client.post(
        "/api/auth/forgot-password",
        json={"email": "nonexistent@test.com"},
        headers={"x-tenant-host": "acme.local"},
    )
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_super_admin_login_on_admin_domain(client: AsyncClient, seeded_data):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "superadmin@test.com", "password": "password123"},
        headers={"x-tenant-host": "admin.local"},
    )
    assert resp.status_code == 200
    assert resp.json()["user"]["role"] == "super_admin"


@pytest.mark.asyncio
async def test_non_super_admin_cannot_login_on_admin_domain(client: AsyncClient, seeded_data):
    resp = await client.post(
        "/api/auth/login",
        json={"email": "admin@acme-test.com", "password": "password123"},
        headers={"x-tenant-host": "admin.local"},
    )
    assert resp.status_code == 403
