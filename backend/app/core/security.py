"""Password hashing (argon2id), JWT access tokens, and opaque refresh tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from functools import lru_cache

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from pydantic import BaseModel, ValidationError

from app.core.config import JWTAlgorithm, Settings
from app.core.errors import UnauthorizedError
from app.core.rbac import Role
from app.utils.datetime import utc_now

ACCESS_TOKEN_TYPE = "access"

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(hashed: str, password: str) -> bool:
    try:
        return _password_hasher.verify(hashed, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    return _password_hasher.check_needs_rehash(hashed)


class TokenPayload(BaseModel):
    sub: str
    role: Role
    type: str
    jti: str
    iat: int
    exp: int
    iss: str
    aud: str


@lru_cache(maxsize=4)
def _read_key(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _signing_key(settings: Settings) -> str:
    if settings.jwt_algorithm is JWTAlgorithm.RS256:
        assert settings.jwt_private_key_path is not None
        return _read_key(settings.jwt_private_key_path)
    return settings.jwt_secret_key


def _verification_key(settings: Settings) -> str:
    if settings.jwt_algorithm is JWTAlgorithm.RS256:
        assert settings.jwt_public_key_path is not None
        return _read_key(settings.jwt_public_key_path)
    return settings.jwt_secret_key


def create_access_token(
    *,
    subject: uuid.UUID | str,
    role: Role,
    settings: Settings,
) -> tuple[str, datetime]:
    """Create a signed access JWT. Returns ``(token, expires_at)``."""
    now = utc_now()
    expires_at = now + settings.access_token_ttl_delta()
    claims = {
        "sub": str(subject),
        "role": role.value,
        "type": ACCESS_TOKEN_TYPE,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    token = jwt.encode(claims, _signing_key(settings), algorithm=settings.jwt_algorithm.value)
    return token, expires_at


def decode_access_token(token: str, settings: Settings) -> TokenPayload:
    """Decode and validate an access JWT; raises :class:`UnauthorizedError` on failure."""
    try:
        claims = jwt.decode(
            token,
            _verification_key(settings),
            algorithms=[settings.jwt_algorithm.value],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "exp", "iat", "iss", "aud", "jti", "type", "role"]},
        )
        payload = TokenPayload.model_validate(claims)
    except (jwt.PyJWTError, ValidationError) as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc
    if payload.type != ACCESS_TOKEN_TYPE:
        raise UnauthorizedError("Invalid token type.")
    return payload


def try_extract_subject(token: str, settings: Settings) -> str | None:
    """Best-effort subject extraction (used for rate-limit keying, never for authz)."""
    try:
        return decode_access_token(token, settings).sub
    except UnauthorizedError:
        return None


def generate_refresh_token() -> tuple[str, str]:
    """Generate an opaque refresh token. Returns ``(token, sha256_hash)``.

    Only the hash is persisted, so a database leak does not leak usable tokens.
    """
    token = secrets.token_urlsafe(48)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
