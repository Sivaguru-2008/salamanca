"""Security response headers (OWASP secure-headers baseline)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        headers = response.headers
        headers.setdefault("X-Content-Type-Options", "nosniff")
        docs_paths = ("/docs", "/redoc", "/openapi.json")
        if request.url.path.startswith(docs_paths):
            # The frontend developer console embeds Swagger in an iframe, so
            # docs pages allow framing from the configured CORS origins only.
            ancestors = " ".join(self.settings.cors_origins) or "'none'"
            headers.setdefault("Content-Security-Policy", f"frame-ancestors {ancestors}")
        else:
            headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "no-referrer")
        headers.setdefault("X-XSS-Protection", "0")
        headers.setdefault(
            "Permissions-Policy", "geolocation=(), camera=(), microphone=(), payment=()"
        )
        if request.url.path.startswith(self.settings.api_v1_prefix):
            # API responses carry sensitive financial data — never cache them,
            # and they are pure JSON so lock the CSP down completely.
            headers.setdefault("Cache-Control", "no-store")
            headers.setdefault(
                "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
            )
        if self.settings.is_production:
            headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        return response
