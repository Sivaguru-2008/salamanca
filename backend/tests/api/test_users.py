from __future__ import annotations

from app.core.rbac import Role
from fastapi import FastAPI
from httpx import AsyncClient

from tests.helpers import auth_headers, create_user_with_role, login_user, register_user


class TestMe:
    async def test_me_requires_auth(self, client: AsyncClient) -> None:
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")

    async def test_me_returns_profile(self, client: AsyncClient) -> None:
        await register_user(client, email="me@example.com", full_name="Me Myself")
        tokens = await login_user(client, email="me@example.com")
        response = await client.get("/api/v1/users/me", headers=auth_headers(tokens))
        assert response.status_code == 200
        body = response.json()
        assert body["email"] == "me@example.com"
        assert body["full_name"] == "Me Myself"

    async def test_patch_me_updates_name(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)
        response = await client.patch(
            "/api/v1/users/me",
            json={"full_name": "Renamed Owner"},
            headers=auth_headers(tokens),
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "Renamed Owner"

    async def test_patch_me_changes_password(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)
        response = await client.patch(
            "/api/v1/users/me",
            json={"password": "brand-new-password"},
            headers=auth_headers(tokens),
        )
        assert response.status_code == 200
        relogin = await login_user(client, password="brand-new-password")
        assert relogin["access_token"]

    async def test_invalid_token_rejected(self, client: AsyncClient) -> None:
        response = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer bogus.token.here"}
        )
        assert response.status_code == 401


class TestAdminListing:
    async def test_owner_cannot_list_users(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)
        response = await client.get("/api/v1/users", headers=auth_headers(tokens))
        assert response.status_code == 403
        assert response.json()["type"].endswith("/forbidden")

    async def test_admin_lists_with_pagination_filter_sort(
        self, app: FastAPI, client: AsyncClient
    ) -> None:
        await create_user_with_role(app, email="admin@example.com", role=Role.ADMIN)
        for i in range(5):
            await register_user(client, email=f"user{i}@example.com")

        tokens = await login_user(client, email="admin@example.com")
        headers = auth_headers(tokens)

        # Page 1
        response = await client.get(
            "/api/v1/users",
            params={"limit": 3, "sort": "email"},
            headers=headers,
        )
        assert response.status_code == 200
        page1 = response.json()
        assert page1["total"] == 6
        assert len(page1["items"]) == 3
        assert page1["next_cursor"]

        # Page 2 via cursor
        response = await client.get(
            "/api/v1/users",
            params={"limit": 3, "sort": "email", "cursor": page1["next_cursor"]},
            headers=headers,
        )
        page2 = response.json()
        assert len(page2["items"]) == 3
        assert page2["next_cursor"] is None
        emails = [u["email"] for u in page1["items"] + page2["items"]]
        assert emails == sorted(emails)

        # Filtering
        response = await client.get(
            "/api/v1/users",
            params={"filter": "role:eq:admin"},
            headers=headers,
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["email"] == "admin@example.com"

        # ilike filter
        response = await client.get(
            "/api/v1/users",
            params={"filter": "email:ilike:user3"},
            headers=headers,
        )
        assert response.json()["total"] == 1

    async def test_bad_filter_field_rejected(self, app: FastAPI, client: AsyncClient) -> None:
        await create_user_with_role(app, email="admin2@example.com", role=Role.ADMIN)
        tokens = await login_user(client, email="admin2@example.com")
        response = await client.get(
            "/api/v1/users",
            params={"filter": "hashed_password:eq:x"},
            headers=auth_headers(tokens),
        )
        assert response.status_code == 422
        assert response.json()["type"].endswith("/validation-error")
