from __future__ import annotations

from app.infra.db.base import Base
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from tests.conftest import build_test_app, make_test_settings


async def test_rate_limit_enforced_and_reported() -> None:
    settings = make_test_settings(rate_limit_requests=3, rate_limit_window_seconds=60)
    app = await build_test_app(settings)

    async with LifespanManager(app):
        engine = app.state.db_engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            payload = {"email": "nobody@example.com", "password": "irrelevant"}

            for attempt in range(3):
                response = await client.post("/api/v1/auth/login", json=payload)
                assert response.status_code == 401
                assert response.headers["X-RateLimit-Limit"] == "3"
                assert int(response.headers["X-RateLimit-Remaining"]) == 3 - (attempt + 1)

            blocked = await client.post("/api/v1/auth/login", json=payload)
            assert blocked.status_code == 429
            assert blocked.headers["content-type"].startswith("application/problem+json")
            assert blocked.headers["X-RateLimit-Remaining"] == "0"
            assert int(blocked.headers["Retry-After"]) > 0
            assert blocked.json()["type"].endswith("/rate-limited")


async def test_health_endpoints_exempt_from_rate_limit() -> None:
    settings = make_test_settings(rate_limit_requests=2, rate_limit_window_seconds=60)
    app = await build_test_app(settings)

    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            for _ in range(10):
                response = await client.get("/healthz")
                assert response.status_code == 200
