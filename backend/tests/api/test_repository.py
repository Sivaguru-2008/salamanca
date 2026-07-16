from __future__ import annotations

from app.core.filtering import parse_filters, parse_sort
from app.core.security import hash_password
from app.infra.db.models.user import User
from app.infra.db.repositories.users import UserRepository
from fastapi import FastAPI

FIELDS = frozenset({"email", "role", "is_active", "created_at"})


def _user(email: str) -> User:
    return User(email=email, hashed_password=hash_password("irrelevant-pw"))


async def test_soft_delete_hides_rows_by_default(app: FastAPI) -> None:
    sessionmaker = app.state.db_sessionmaker
    async with sessionmaker() as session:
        repo = UserRepository(session)
        user = await repo.add(_user("gone@example.com"))
        await repo.soft_delete(user)
        await session.commit()

    async with sessionmaker() as session:
        repo = UserRepository(session)
        assert await repo.get(user.id) is None
        assert await repo.get(user.id, include_deleted=True) is not None
        assert await repo.get_by_email("gone@example.com") is None


async def test_list_with_filters_sort_and_count(app: FastAPI) -> None:
    sessionmaker = app.state.db_sessionmaker
    async with sessionmaker() as session:
        repo = UserRepository(session)
        for name in ("carol", "alice", "bob"):
            await repo.add(_user(f"{name}@example.com"))
        await session.commit()

    async with sessionmaker() as session:
        repo = UserRepository(session)

        items, total = await repo.list(sort=parse_sort("email", FIELDS), limit=2, offset=0)
        assert total == 3
        assert [u.email for u in items] == ["alice@example.com", "bob@example.com"]

        items, total = await repo.list(
            filters=parse_filters(["email:ilike:bob"], FIELDS),
            sort=parse_sort("email", FIELDS),
            limit=10,
            offset=0,
        )
        assert total == 1
        assert items[0].email == "bob@example.com"

        items, total = await repo.list(
            filters=parse_filters(["is_active:eq:true"], FIELDS),
            sort=parse_sort("-email", FIELDS),
            limit=10,
            offset=0,
        )
        assert total == 3
        assert items[0].email == "carol@example.com"

        assert await repo.count() == 3
        in_filter = parse_filters(["email:in:alice@example.com,bob@example.com"], FIELDS)
        assert await repo.count(filters=in_filter) == 2


async def test_update_and_hard_delete(app: FastAPI) -> None:
    sessionmaker = app.state.db_sessionmaker
    async with sessionmaker() as session:
        repo = UserRepository(session)
        user = await repo.add(_user("temp@example.com"))
        await repo.update(user, full_name="Updated Name")
        assert user.full_name == "Updated Name"
        await repo.delete(user)
        await session.commit()

    async with sessionmaker() as session:
        repo = UserRepository(session)
        assert await repo.get_by_email("temp@example.com") is None
