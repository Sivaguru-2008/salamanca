"""Request validation middleware: payload size cap and content-type allowlist."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import Settings
from app.core.errors import PROBLEM_CONTENT_TYPE, build_problem

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH"})
_ALLOWED_CONTENT_TYPES = (
    "application/json",
    "application/x-www-form-urlencoded",
    "multipart/form-data",
)


class BodyLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, settings: Settings) -> None:
        super().__init__(app)
        self.max_bytes = settings.max_request_body_bytes
        self.api_prefix = settings.api_v1_prefix

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method not in _BODY_METHODS or not request.url.path.startswith(self.api_prefix):
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = -1
            if size < 0 or size > self.max_bytes:
                problem = build_problem(
                    request,
                    status_code=413,
                    error_code="payload-too-large",
                    title="Payload Too Large",
                    detail=f"Request body exceeds the {self.max_bytes} byte limit.",
                )
                return JSONResponse(
                    status_code=413,
                    content=problem.model_dump(exclude_none=True),
                    media_type=PROBLEM_CONTENT_TYPE,
                )

        content_type = request.headers.get("content-type", "")
        has_body = content_length not in (None, "0")
        if has_body and content_type:
            base_type = content_type.split(";", 1)[0].strip().lower()
            if base_type and not base_type.startswith(_ALLOWED_CONTENT_TYPES):
                problem = build_problem(
                    request,
                    status_code=415,
                    error_code="unsupported-media-type",
                    title="Unsupported Media Type",
                    detail=f"Content type '{base_type}' is not accepted by this API.",
                )
                return JSONResponse(
                    status_code=415,
                    content=problem.model_dump(exclude_none=True),
                    media_type=PROBLEM_CONTENT_TYPE,
                )

        return await call_next(request)
