"""RED metrics per route template."""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match, Route
from starlette.types import ASGIApp

from app.core.metrics import (
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_IN_PROGRESS,
    HTTP_REQUESTS_TOTAL,
)

_SKIP_PATHS = frozenset({"/metrics", "/healthz", "/livez", "/readyz"})


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    if isinstance(route, Route):
        return route.path
    # Fall back to matching against the app's route table (route not yet bound).
    for candidate in request.app.routes:
        if isinstance(candidate, Route):
            match, _ = candidate.matches(request.scope)
            if match == Match.FULL:
                return candidate.path
    return "unmatched"


class MetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        HTTP_REQUESTS_IN_PROGRESS.inc()
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.perf_counter() - start
            HTTP_REQUESTS_IN_PROGRESS.dec()
            path = _route_template(request)
            HTTP_REQUESTS_TOTAL.labels(
                method=request.method, path=path, status=str(status_code)
            ).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(method=request.method, path=path).observe(duration)
