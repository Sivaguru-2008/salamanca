from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from app.api.v1.schemas.common import PROBLEM_RESPONSES, Message
from app.api.v1.schemas.users import UserRead
from app.domain.auth.service import AuthService
from app.domain.users.service import UserService

router = APIRouter(prefix="/auth", tags=["auth"], responses=PROBLEM_RESPONSES)


def _client_meta(request: Request) -> tuple[str, str]:
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host if request.client else ""
    return user_agent, ip_address


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
)
async def register(payload: RegisterRequest, db: DbSession) -> UserRead:
    user = await UserService(db).register(
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPair, summary="Issue access + refresh tokens")
async def login(
    payload: LoginRequest,
    request: Request,
    db: DbSession,
    settings: SettingsDep,
) -> TokenPair:
    user_agent, ip_address = _client_meta(request)
    tokens = await AuthService(db, settings).login(
        email=payload.email,
        password=payload.password,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/refresh", response_model=TokenPair, summary="Rotate the refresh token")
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: DbSession,
    settings: SettingsDep,
) -> TokenPair:
    user_agent, ip_address = _client_meta(request)
    tokens = await AuthService(db, settings).refresh(
        refresh_token=payload.refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/logout", response_model=Message, summary="Revoke refresh session(s)")
async def logout(
    payload: LogoutRequest,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
) -> Message:
    revoked = await AuthService(db, settings).logout(
        user,
        refresh_token=payload.refresh_token,
        everywhere=payload.everywhere,
    )
    return Message(message=f"Revoked {revoked} session(s).")
