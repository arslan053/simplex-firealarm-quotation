import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import get_db
from app.main import app
from app.shared.base_model import Base
from app.shared.security import create_access_token, hash_password

TEST_DATABASE_URL = settings.DATABASE_URL

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_data(db_session: AsyncSession):
    """Create test tenants and users."""
    from app.modules.tenants.models import Tenant
    from app.modules.users.models import User

    acme = Tenant(name="Acme Corp", slug="acme", status="active")
    beta = Tenant(name="Beta Inc", slug="beta", status="active")
    suspended = Tenant(name="Suspended Co", slug="suspended", status="suspended")
    db_session.add_all([acme, beta, suspended])
    await db_session.flush()

    super_admin = User(
        email="superadmin@test.com",
        name="Super Admin",
        password_hash=hash_password("password123"),
        role="super_admin",
        tenant_id=None,
        is_active=True,
    )
    acme_admin = User(
        email="admin@acme-test.com",
        name="Acme Admin",
        password_hash=hash_password("password123"),
        role="admin",
        tenant_id=acme.id,
        is_active=True,
    )
    acme_employee = User(
        email="employee@acme-test.com",
        name="Acme Employee",
        password_hash=hash_password("password123"),
        role="employee",
        tenant_id=acme.id,
        is_active=True,
    )
    beta_admin = User(
        email="admin@beta-test.com",
        name="Beta Admin",
        password_hash=hash_password("password123"),
        role="admin",
        tenant_id=beta.id,
        is_active=True,
    )
    beta_employee = User(
        email="employee@beta-test.com",
        name="Beta Employee",
        password_hash=hash_password("password123"),
        role="employee",
        tenant_id=beta.id,
        is_active=True,
    )
    db_session.add_all([super_admin, acme_admin, acme_employee, beta_admin, beta_employee])
    await db_session.flush()

    return {
        "acme": acme,
        "beta": beta,
        "suspended": suspended,
        "super_admin": super_admin,
        "acme_admin": acme_admin,
        "acme_employee": acme_employee,
        "beta_admin": beta_admin,
        "beta_employee": beta_employee,
    }


def make_token(user) -> str:
    return create_access_token(
        user_id=str(user.id),
        role=user.role,
        tenant_id=str(user.tenant_id) if user.tenant_id else None,
    )
