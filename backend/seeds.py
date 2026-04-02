"""Seed script: creates initial tenants and users for local development."""

import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, engine
from app.modules.tenants.models import Tenant
from app.modules.users.models import User
from app.shared.security import hash_password

DEFAULT_PASSWORD = "admin123"


async def seed():
    async with async_session_factory() as db:
        # Check if already seeded
        result = await db.execute(select(User).where(User.email == "superadmin@app.com"))
        if result.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        # Super admin
        super_admin = User(
            email="superadmin@app.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="super_admin",
            tenant_id=None,
            must_change_password=False,
            is_active=True,
        )
        db.add(super_admin)

        # Tenants
        acme = Tenant(name="Acme Corp", slug="acme", status="active")
        beta = Tenant(name="Beta Inc", slug="beta", status="active")
        db.add(acme)
        db.add(beta)
        await db.flush()

        # Acme users
        acme_admin = User(
            email="admin@acme.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="admin",
            tenant_id=acme.id,
            must_change_password=False,
            is_active=True,
        )
        acme_emp1 = User(
            email="employee1@acme.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="employee",
            tenant_id=acme.id,
            must_change_password=False,
            is_active=True,
        )
        acme_emp2 = User(
            email="employee2@acme.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="employee",
            tenant_id=acme.id,
            must_change_password=False,
            is_active=True,
        )
        db.add_all([acme_admin, acme_emp1, acme_emp2])

        # Beta users
        beta_admin = User(
            email="admin@beta.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="admin",
            tenant_id=beta.id,
            must_change_password=False,
            is_active=True,
        )
        beta_emp1 = User(
            email="employee1@beta.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="employee",
            tenant_id=beta.id,
            must_change_password=False,
            is_active=True,
        )
        beta_emp2 = User(
            email="employee2@beta.com",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role="employee",
            tenant_id=beta.id,
            must_change_password=False,
            is_active=True,
        )
        db.add_all([beta_admin, beta_emp1, beta_emp2])

        await db.commit()
        print("Seed data created successfully!")
        print(f"  Super admin: superadmin@app.com / {DEFAULT_PASSWORD}")
        print(f"  Acme admin:  admin@acme.com / {DEFAULT_PASSWORD}")
        print(f"  Beta admin:  admin@beta.com / {DEFAULT_PASSWORD}")


async def main():
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
