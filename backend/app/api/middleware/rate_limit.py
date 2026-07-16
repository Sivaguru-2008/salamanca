"""Redis fixed-window rate limiting per principal (authenticated user or IP).

Fails open: if Redis is unavailable the request proceeds and the incident is
logged — availability of the API is preferred over strict limiting.
"""

from __future__ import annotations

import structlog
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import Settings
from app.core.errors import PROBLEM_CONTENT_TYPE, build_problem
from app.core.metrics import RATE_LIMITED_TOTAL
from app.core.security import try_extract_subject

logger = structlog.get_logger(__name__)

_EXEMPT_PATHS = frozenset(
    {"/healthz", "/livez", "/readyz", "/metrics", "/docs", "/redoc", "/openapi.json"}
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    def _principal(self, request: Request) -> str:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            subject = try_extract_subject(auth[7:].strip(), self.settings)
            if subject:
                return f"user:{subject}"
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if (
            not self.settings.rate_limit_enabled
            or request.method == "OPTIONS"
            or request.url.path in _EXEMPT_PATHS
        ):
            return await call_next(request)

        limit = self.settings.rate_limit_requests
        window = self.settings.rate_limit_window_seconds
        principal = self._principal(request)
        key = f"fios:rl:{principal}:{request.url.path}"

        try:
            redis = request.app.state.redis
            current = await redis.incr(key)
            ttl = await redis.ttl(key)
            if ttl == -1:
                await redis.expire(key, window)
                ttl = window
        except RedisError as exc:
            logger.warning("rate_limit_backend_unavailable", error=str(exc))
            return await call_next(request)

        reset_seconds = ttl if ttl and ttl > 0 else window

        if current > limit:
            RATE_LIMITED_TOTAL.labels(path=request.url.path).inc()
            problem = build_problem(
                request,
                status_code=429,
                error_code="rate-limited",
                title="Too Many Requests",
                detail="Rate limit exceeded. Slow down and retry later.",
            )
            return JSONResponse(
                status_code=429,
                content=problem.model_dump(exclude_none=True),
                media_type=PROBLEM_CONTENT_TYPE,
                headers={
                    "Retry-After": str(reset_seconds),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_seconds),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(limit - current, 0))
        response.headers["X-RateLimit-Reset"] = str(reset_seconds)
        return response
