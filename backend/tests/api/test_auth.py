from __future__ import annotations

from httpx import AsyncClient

from tests.helpers import DEFAULT_PASSWORD, auth_headers, login_user, register_user


class TestRegister:
    async def test_register_creates_user(self, client: AsyncClient) -> None:
        body = await register_user(client, email="alice@example.com")
        assert body["email"] == "alice@example.com"
        assert body["role"] == "owner"
        assert "hashed_password" not in body

    async def test_email_is_normalized(self, client: AsyncClient) -> None:
        body = await register_user(client, email="Bob@Example.COM ")
        assert body["email"] == "bob@example.com"

    async def test_duplicate_email_conflicts(self, client: AsyncClient) -> None:
        await register_user(client, email="dup@example.com")
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "dup@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 409
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["type"].endswith("/conflict")

    async def test_short_password_rejected(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "short"},
        )
        assert response.status_code == 422
        problem = response.json()
        assert problem["type"].endswith("/validation-error")
        assert any(e["field"].endswith("password") for e in problem["errors"])


class TestLogin:
    async def test_login_returns_token_pair(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] > 0
        assert tokens["access_token"] != tokens["refresh_token"]

    async def test_wrong_password_unauthorized(self, client: AsyncClient) -> None:
        await register_user(client)
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "owner@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/problem+json")

    async def test_unknown_user_unauthorized(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": DEFAULT_PASSWORD},
        )
        assert response.status_code == 401


class TestRefreshRotation:
    async def test_refresh_rotates_tokens(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert response.status_code == 200
        rotated = response.json()
        assert rotated["refresh_token"] != tokens["refresh_token"]
        assert rotated["access_token"]

    async def test_reuse_of_rotated_token_revokes_everything(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)

        first = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert first.status_code == 200
        rotated = first.json()

        # Replay the original (now rotated) token → breach response.
        reuse = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert reuse.status_code == 401
        assert "reuse" in reuse.json()["detail"].lower()

        # The successor session must also have been revoked.
        after_breach = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
        )
        assert after_breach.status_code == 401

    async def test_unknown_refresh_token_rejected(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "a" * 64})
        assert response.status_code == 401


class TestLogout:
    async def test_logout_revokes_session(self, client: AsyncClient) -> None:
        await register_user(client)
        tokens = await login_user(client)

        response = await client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
            headers=auth_headers(tokens),
        )
        assert response.status_code == 200
        assert "1 session" in response.json()["message"]

        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )
        assert refresh.status_code == 401

    async def test_logout_everywhere(self, client: AsyncClient) -> None:
        await register_user(client)
        first = await login_user(client)
        second = await login_user(client)

        response = await client.post(
            "/api/v1/auth/logout",
            json={"everywhere": True},
            headers=auth_headers(second),
        )
        assert response.status_code == 200

        for tokens in (first, second):
            refresh = await client.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            )
            assert refresh.status_code == 401

    async def test_logout_requires_auth(self, client: AsyncClient) -> None:
        response = await client.post("/api/v1/auth/logout", json={})
        assert response.status_code == 401
