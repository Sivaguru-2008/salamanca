"""Authentication service: login, rotating refresh tokens, revocation.

Refresh tokens are opaque, stored hashed, and single-use. Presenting an
already-rotated/revoked token is treated as a breach signal: every session
belonging to that user is revoked (see 06-api-security §3.2).
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.infra.db.models.auth_session import AuthSession
from app.infra.db.models.user import User
from app.infra.db.repositories.auth_sessions import AuthSessionRepository
from app.infra.db.repositories.users import UserRepository
from app.infra.db.session import session_scope
from app.utils.datetime import days_ago, is_expired, utc_now

logger = structlog.get_logger(__name__)

_INVALID_CREDENTIALS = "Invalid email or password."
_INVALID_REFRESH = "Invalid or expired refresh token."


@dataclass(slots=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.sessions = AuthSessionRepository(session)

    async def _issue_tokens(
        self,
        user: User,
        *,
        user_agent: str,
        ip_address: str,
    ) -> IssuedTokens:
        refresh_token, token_hash = generate_refresh_token()
        session_row = AuthSession(
            user_id=user.id,
            refresh_token_hash=token_hash,
            user_agent=user_agent[:400],
            ip_address=ip_address[:64],
            expires_at=utc_now() + self.settings.refresh_token_ttl_delta(),
        )
        await self.sessions.add(session_row)
        access_token, _ = create_access_token(
            subject=user.id, role=user.role, settings=self.settings
        )
        return IssuedTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_ttl_seconds,
        )

    async def login(
        self,
        *,
        email: str,
        password: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> IssuedTokens:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(user.hashed_password, password):
            raise UnauthorizedError(_INVALID_CREDENTIALS)
        if not user.is_active:
            raise UnauthorizedError("This account is disabled.")

        await self.users.update(user, last_login_at=utc_now())
        tokens = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        logger.info("user_logged_in", user_id=str(user.id))
        return tokens

    async def refresh(
        self,
        *,
        refresh_token: str,
        user_agent: str = "",
        ip_address: str = "",
    ) -> IssuedTokens:
        token_hash = hash_refresh_token(refresh_token)
        session_row = await self.sessions.get_by_token_hash(token_hash)
        if session_row is None:
            raise UnauthorizedError(_INVALID_REFRESH)

        if session_row.is_revoked:
            # Token reuse after rotation → assume compromise, revoke everything.
            revoked = await self.sessions.revoke_all_for_user(session_row.user_id)
            # Commit now: the 401 raised below rolls back the request transaction,
            # but the breach response must persist regardless.
            await self.session.commit()
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=str(session_row.user_id),
                sessions_revoked=revoked,
            )
            raise UnauthorizedError("Refresh token reuse detected. All sessions revoked.")

        if is_expired(session_row.expires_at):
            raise UnauthorizedError(_INVALID_REFRESH)

        user = await self.users.get(session_row.user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError(_INVALID_REFRESH)

        session_row.last_used_at = utc_now()
        tokens = await self._issue_tokens(user, user_agent=user_agent, ip_address=ip_address)
        new_row = await self.sessions.get_by_token_hash(hash_refresh_token(tokens.refresh_token))
        assert new_row is not None
        await self.sessions.revoke(session_row, replaced_by=new_row.id)
        return tokens

    async def logout(
        self,
        user: User,
        *,
        refresh_token: str | None = None,
        everywhere: bool = False,
    ) -> int:
        """Revoke the presented session (or all of the user's sessions)."""
        if everywhere or not refresh_token:
            return await self.sessions.revoke_all_for_user(user.id)

        session_row = await self.sessions.get_by_token_hash(hash_refresh_token(refresh_token))
        if session_row is None or session_row.user_id != user.id or session_row.is_revoked:
            return 0
        await self.sessions.revoke(session_row)
        return 1


async def purge_stale_auth_sessions(
    sessionmaker: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    """Periodic maintenance: hard-delete long-expired/revoked refresh sessions."""
    cutoff = days_ago(settings.auth_session_retention_days)
    async with session_scope(sessionmaker) as session:
        removed = await AuthSessionRepository(session).purge_stale(cutoff)
    if removed:
        logger.info("auth_sessions_purged", removed=removed)
