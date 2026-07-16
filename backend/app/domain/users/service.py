"""User lifecycle service.

Purpose: registration, profile management, and administrative listing.
Inputs: validated primitives from the API layer.
Outputs: ORM ``User`` aggregates (serialized by the router DTOs).
Failure: raises typed ``AppError`` subclasses; never leaks raw DB errors.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.core.filtering import FieldFilter, SortField
from app.core.rbac import Role
from app.core.security import hash_password
from app.infra.db.models.user import User
from app.infra.db.repositories.users import UserRepository

USER_FILTERABLE_FIELDS = frozenset(
    {"email", "full_name", "role", "is_active", "is_verified", "created_at", "last_login_at"}
)
USER_SORTABLE_FIELDS = frozenset({"email", "full_name", "role", "created_at", "last_login_at"})


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)

    async def register(
        self,
        *,
        email: str,
        password: str,
        full_name: str = "",
        role: Role = Role.OWNER,
        is_verified: bool = False,
        created_by: uuid.UUID | None = None,
    ) -> User:
        normalized = email.strip().lower()
        if await self.users.email_exists(normalized):
            raise ConflictError("An account with this email already exists.")
        user = User(
            email=normalized,
            hashed_password=hash_password(password),
            full_name=full_name.strip(),
            role=role,
            is_active=True,
            is_verified=is_verified,
            created_by=created_by,
        )
        return await self.users.add(user)

    async def get(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def update_profile(
        self,
        user: User,
        *,
        full_name: str | None = None,
        password: str | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> User:
        values: dict[str, object] = {}
        if full_name is not None:
            values["full_name"] = full_name.strip()
        if password is not None:
            values["hashed_password"] = hash_password(password)
        if values:
            values["updated_by"] = actor_id or user.id
            await self.users.update(user, **values)
        return user

    async def list_users(
        self,
        *,
        filters: Sequence[FieldFilter],
        sort: Sequence[SortField],
        limit: int,
        offset: int,
    ) -> tuple[list[User], int]:
        return await self.users.list(filters=filters, sort=sort, limit=limit, offset=offset)
