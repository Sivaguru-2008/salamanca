from __future__ import annotations

from sqlalchemy import func, select

from app.infra.db.models.user import User
from app.infra.db.repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = self._base_select().where(func.lower(User.email) == email.strip().lower())
        return await self.session.scalar(stmt)

    async def email_exists(self, email: str) -> bool:
        stmt = select(func.count(User.id)).where(func.lower(User.email) == email.strip().lower())
        count = await self.session.scalar(stmt)
        return bool(count)
