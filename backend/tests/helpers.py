"""Reusable flows for API tests."""

from __future__ import annotations

from typing import Any

from app.core.rbac import Role
from app.domain.users.service import UserService
from fastapi import FastAPI
from httpx import AsyncClient

DEFAULT_PASSWORD = "str0ng-passw0rd"


async def register_user(
    client: AsyncClient,
    *,
    email: str = "owner@example.com",
    password: str = DEFAULT_PASSWORD,
    full_name: str = "Test Owner",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return dict(response.json())


async def login_user(
    client: AsyncClient,
    *,
    email: str = "owner@example.com",
    password: str = DEFAULT_PASSWORD,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def auth_headers(tokens: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


async def create_user_with_role(
    app: FastAPI,
    *,
    email: str,
    password: str = DEFAULT_PASSWORD,
    role: Role = Role.OWNER,
) -> None:
    """Create a user directly through the service layer (bypasses the API)."""
    sessionmaker = app.state.db_sessionmaker
    async with sessionmaker() as session:
        await UserService(session).register(
            email=email,
            password=password,
            role=role,
            is_verified=True,
        )
        await session.commit()
