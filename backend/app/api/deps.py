"""FastAPI dependency-injection providers."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, PageParams
from app.core.rbac import Permission, has_all_permissions
from app.core.security import decode_access_token
from app.infra.db.models.user import User
from app.infra.db.repositories.users import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_redis(request: Request) -> Redis:
    redis: Redis = request.app.state.redis
    return redis


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """Request-scoped unit of work: commit on success, rollback on error."""
    sessionmaker = request.app.state.db_sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
RedisDep = Annotated[Redis, Depends(get_redis)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)] = None,
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token.")
    payload = decode_access_token(credentials.credentials, settings)
    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise UnauthorizedError("Invalid token subject.") from exc
    user = await UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Account is disabled or no longer exists.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_permissions(*permissions: Permission):  # type: ignore[no-untyped-def]
    """Route guard: the authenticated principal's role must grant every permission."""
    required = frozenset(permissions)

    async def _checker(user: CurrentUser) -> User:
        if not has_all_permissions(user.role, required):
            raise ForbiddenError("You do not have permission to perform this action.")
        return user

    return _checker


def pagination_params(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_LIMIT)] = DEFAULT_PAGE_LIMIT,
    cursor: Annotated[str | None, Query(description="Opaque pagination cursor.")] = None,
) -> PageParams:
    return PageParams.from_query(limit=limit, cursor=cursor)


Pagination = Annotated[PageParams, Depends(pagination_params)]
