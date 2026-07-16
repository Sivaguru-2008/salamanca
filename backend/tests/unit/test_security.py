from __future__ import annotations

import pytest
from app.core.errors import UnauthorizedError
from app.core.rbac import Role
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    try_extract_subject,
    verify_password,
)
from app.utils.uuid7 import uuid7

from tests.conftest import make_test_settings


class TestPasswordHashing:
    def test_hash_and_verify_roundtrip(self) -> None:
        hashed = hash_password("s3cret-password")
        assert hashed != "s3cret-password"
        assert hashed.startswith("$argon2")
        assert verify_password(hashed, "s3cret-password")

    def test_wrong_password_rejected(self) -> None:
        hashed = hash_password("s3cret-password")
        assert not verify_password(hashed, "wrong-password")

    def test_garbage_hash_rejected(self) -> None:
        assert not verify_password("not-a-hash", "anything")


class TestAccessTokens:
    def test_roundtrip(self) -> None:
        settings = make_test_settings()
        user_id = uuid7()
        token, expires_at = create_access_token(subject=user_id, role=Role.OWNER, settings=settings)
        payload = decode_access_token(token, settings)
        assert payload.sub == str(user_id)
        assert payload.role is Role.OWNER
        assert payload.type == "access"
        assert payload.exp == int(expires_at.timestamp())

    def test_tampered_token_rejected(self) -> None:
        settings = make_test_settings()
        token, _ = create_access_token(subject=uuid7(), role=Role.OWNER, settings=settings)
        with pytest.raises(UnauthorizedError):
            decode_access_token(token + "x", settings)

    def test_wrong_secret_rejected(self) -> None:
        settings = make_test_settings()
        other = make_test_settings(jwt_secret_key="a-different-secret-key-of-sufficient-length")
        token, _ = create_access_token(subject=uuid7(), role=Role.OWNER, settings=settings)
        with pytest.raises(UnauthorizedError):
            decode_access_token(token, other)

    def test_try_extract_subject(self) -> None:
        settings = make_test_settings()
        user_id = uuid7()
        token, _ = create_access_token(subject=user_id, role=Role.OWNER, settings=settings)
        assert try_extract_subject(token, settings) == str(user_id)
        assert try_extract_subject("garbage", settings) is None


class TestRefreshTokens:
    def test_generate_returns_token_and_hash(self) -> None:
        token, token_hash = generate_refresh_token()
        assert len(token) >= 48
        assert token_hash == hash_refresh_token(token)
        assert len(token_hash) == 64

    def test_tokens_are_unique(self) -> None:
        tokens = {generate_refresh_token()[0] for _ in range(50)}
        assert len(tokens) == 50
