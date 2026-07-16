from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, Pagination, require_permissions
from app.api.v1.schemas.common import PROBLEM_RESPONSES
from app.api.v1.schemas.users import UserRead, UserUpdate
from app.core.filtering import parse_filters, parse_sort
from app.core.pagination import Page
from app.core.rbac import Permission
from app.domain.users.service import (
    USER_FILTERABLE_FIELDS,
    USER_SORTABLE_FIELDS,
    UserService,
)
from app.infra.db.models.user import User

router = APIRouter(prefix="/users", tags=["users"], responses=PROBLEM_RESPONSES)


@router.get("/me", response_model=UserRead, summary="Current user profile")
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead, summary="Update current user profile")
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> UserRead:
    updated = await UserService(db).update_profile(
        user,
        full_name=payload.full_name,
        password=payload.password,
    )
    return UserRead.model_validate(updated)


@router.get(
    "",
    response_model=Page[UserRead],
    summary="List users (admin)",
    description=(
        "Cursor-paginated listing. Filters use `filter=field:op:value` "
        "(ops: eq, ne, gt, gte, lt, lte, like, ilike, in); sorting uses "
        "`sort=-created_at,email`."
    ),
)
async def list_users(
    db: DbSession,
    page: Pagination,
    _admin: Annotated[User, Depends(require_permissions(Permission.USER_MANAGE))],
    sort: Annotated[str | None, Query()] = None,
    filters: Annotated[list[str], Query(alias="filter")] = [],  # noqa: B006
) -> Page[UserRead]:
    parsed_filters = parse_filters(filters, USER_FILTERABLE_FIELDS)
    parsed_sort = parse_sort(sort, USER_SORTABLE_FIELDS, default="-created_at")
    users, total = await UserService(db).list_users(
        filters=parsed_filters,
        sort=parsed_sort,
        limit=page.limit,
        offset=page.offset,
    )
    return Page[UserRead].build([UserRead.model_validate(u) for u in users], total, page)
