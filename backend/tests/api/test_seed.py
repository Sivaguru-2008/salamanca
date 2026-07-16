from __future__ import annotations

from app.infra.seed import run_seeders
from fastapi import FastAPI

from tests.conftest import make_test_settings


async def test_admin_seeder_is_idempotent(app: FastAPI) -> None:
    settings = make_test_settings(
        seed_admin_email="seeded-admin@example.com",
        seed_admin_password="seeded-admin-password",
    )
    sessionmaker = app.state.db_sessionmaker

    async with sessionmaker() as session:
        first = await run_seeders(session, settings)
        await session.commit()
    async with sessionmaker() as session:
        second = await run_seeders(session, settings)
        await session.commit()

    outcomes = {r.seeder: r.outcome for r in first}
    assert outcomes["admin-user"] == "created"
    outcomes = {r.seeder: r.outcome for r in second}
    assert outcomes["admin-user"] == "skipped"


async def test_seeder_skips_without_credentials(app: FastAPI) -> None:
    settings = make_test_settings()
    sessionmaker = app.state.db_sessionmaker
    async with sessionmaker() as session:
        results = await run_seeders(session, settings)
    assert all(r.outcome == "skipped" for r in results if r.seeder == "admin-user")
