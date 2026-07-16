from __future__ import annotations

from fastapi import FastAPI
from httpx import AsyncClient


async def test_unknown_route_returns_problem_json(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["status"] == 404
    assert body["instance"] == "/api/v1/does-not-exist"
    assert body["request_id"]


async def test_validation_error_shape(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "x"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["type"].endswith("/validation-error")
    fields = {e["field"] for e in body["errors"]}
    assert any("email" in f for f in fields)
    assert any("password" in f for f in fields)


async def test_method_not_allowed_is_problem_json(client: AsyncClient) -> None:
    response = await client.delete("/api/v1/auth/login")
    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/problem+json")


async def test_security_headers_present_on_api_paths(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


async def test_unsupported_content_type_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        content=b"<xml/>",
        headers={"Content-Type": "application/xml"},
    )
    assert response.status_code == 415
    assert response.json()["type"].endswith("/unsupported-media-type")


async def test_oversized_payload_rejected(app: FastAPI, client: AsyncClient) -> None:
    max_bytes = app.state.settings.max_request_body_bytes
    response = await client.post(
        "/api/v1/auth/login",
        content=b"{}",
        headers={
            "Content-Type": "application/json",
            "Content-Length": str(max_bytes + 1),
        },
    )
    assert response.status_code == 413
    assert response.json()["type"].endswith("/payload-too-large")
