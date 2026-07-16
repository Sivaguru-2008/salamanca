"""Shared test fixtures.

Tests are fully self-contained: SQLite (in-memory, StaticPool) replaces
Postgres and fakeredis replaces Redis, so the suite runs with no services.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import fakeredis.aioredis
import pytest
import pytest_asyncio
from app.core.config import Environment, Settings
from app.infra.db.base import Base
from app.main import create_app
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def make_test_settings(**overrides: Any) -> Settings:
    defaults: dict[str, Any] = {
        "environment": Environment.TESTING,
        "debug": False,
        "database_url": "sqlite+aiosqlite:///:memory:",
        "jwt_secret_key": "test-secret-key-not-for-production",
        "rate_limit_enabled": True,
        "rate_limit_requests": 1000,
        "rate_limit_window_seconds": 60,
        "otel_enabled": False,
        "log_json": False,
        "docs_enabled": True,
        "seed_admin_email": None,
        "seed_admin_password": None,
    }
    defaults.update(overrides)
    return Settings(_env_file=None, **defaults)


async def build_test_app(settings: Settings) -> FastAPI:
    application = create_app(settings)
    application.state.redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return application


@pytest.fixture
def settings() -> Settings:
    return make_test_settings()


@pytest_asyncio.fixture
async def app(settings: Settings) -> AsyncIterator[FastAPI]:
    application = await build_test_app(settings)
    async with LifespanManager(application):
        engine = application.state.db_engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield application


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client
