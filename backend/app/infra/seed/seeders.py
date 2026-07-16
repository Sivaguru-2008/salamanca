"""Built-in seeders."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.rbac import Role
from app.core.security import hash_password
from app.infra.db.models.user import User
from app.infra.db.repositories.users import UserRepository
from app.infra.seed.framework import Seeder, SeedResult, register_seeder


@register_seeder
class AdminUserSeeder(Seeder):
    """Creates the platform admin when seed credentials are configured."""

    name = "admin-user"
    order = 10

    async def run(self, session: AsyncSession, settings: Settings) -> SeedResult:
        if not settings.seed_admin_email or not settings.seed_admin_password:
            return SeedResult(self.name, "skipped", "seed admin credentials not configured")

        repo = UserRepository(session)
        existing = await repo.get_by_email(settings.seed_admin_email)
        if existing is not None:
            return SeedResult(self.name, "skipped", f"admin {existing.email} already exists")

        user = User(
            email=settings.seed_admin_email.strip().lower(),
            hashed_password=hash_password(settings.seed_admin_password),
            full_name="Platform Administrator",
            role=Role.ADMIN,
            is_active=True,
            is_verified=True,
        )
        await repo.add(user)
        return SeedResult(self.name, "created", f"admin {user.email}")
