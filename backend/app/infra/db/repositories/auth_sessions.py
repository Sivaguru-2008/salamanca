from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, cast

from sqlalchemy import CursorResult, delete, or_, update

from app.infra.db.models.auth_session import AuthSession
from app.infra.db.repository import BaseRepository
from app.utils.datetime import utc_now


class AuthSessionRepository(BaseRepository[AuthSession]):
    model = AuthSession

    async def get_by_token_hash(self, token_hash: str) -> AuthSession | None:
        return await self.get_by(refresh_token_hash=token_hash)

    async def revoke(
        self, session_row: AuthSession, *, replaced_by: uuid.UUID | None = None
    ) -> None:
        session_row.revoked_at = utc_now()
        session_row.replaced_by_id = replaced_by
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        stmt = (
            update(AuthSession)
            .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.flush()
        return int(result.rowcount or 0)

    async def purge_stale(self, cutoff: datetime) -> int:
        """Hard-delete sessions that expired or were revoked before ``cutoff``."""
        stmt = delete(AuthSession).where(
            or_(
                AuthSession.expires_at < cutoff,
                AuthSession.revoked_at.is_not(None) & (AuthSession.revoked_at < cutoff),
            )
        )
        result = cast(CursorResult[Any], await self.session.execute(stmt))
        await self.session.flush()
        return int(result.rowcount or 0)
