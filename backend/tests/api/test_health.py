from __future__ import annotations

from httpx import AsyncClient


async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"] == "testing"
    assert "X-Request-ID" in response.headers


async def test_livez(client: AsyncClient) -> None:
    response = await client.get("/livez")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readyz_reports_dependencies(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    checks = {c["name"]: c for c in body["checks"]}
    assert checks["postgres"]["healthy"] is True
    assert checks["redis"]["healthy"] is True


async def test_metrics_exposed(client: AsyncClient) -> None:
    await client.get("/healthz")
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "fios_http_requests_total" in response.text


async def test_request_id_is_propagated(client: AsyncClient) -> None:
    response = await client.get("/healthz", headers={"X-Request-ID": "test-correlation-id"})
    assert response.headers["X-Request-ID"] == "test-correlation-id"
