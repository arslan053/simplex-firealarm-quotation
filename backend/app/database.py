from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_worker_db(tenant_id: str):
    """DB session with RLS tenant context for background workers."""
    async with async_session_factory() as session:
        try:
            await session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_tenant_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """DB session with RLS tenant context set from the resolved tenant."""
    async with async_session_factory() as session:
        try:
            tenant = getattr(request.state, "tenant", None)
            if tenant:
                # SET LOCAL doesn't support bind params in asyncpg;
                # tenant["id"] is already validated UUID from middleware
                tid = str(tenant["id"])
                await session.execute(text(f"SET LOCAL app.tenant_id = '{tid}'"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
