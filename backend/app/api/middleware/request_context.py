"""Request correlation: request id propagation, contextvar binding, access log."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

logger = structlog.get_logger("app.access")

REQUEST_ID_HEADER = "X-Request-ID"
_QUIET_PATHS = frozenset({"/healthz", "/livez", "/readyz", "/metrics"})


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            http_method=request.method,
            http_path=request.url.path,
        )

        start = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[REQUEST_ID_HEADER] = request_id
            if request.url.path not in _QUIET_PATHS:
                logger.info(
                    "request_completed",
                    status_code=response.status_code,
                    duration_ms=round((time.perf_counter() - start) * 1000, 2),
                    client=request.client.host if request.client else None,
                )
            return response
        finally:
            structlog.contextvars.clear_contextvars()
