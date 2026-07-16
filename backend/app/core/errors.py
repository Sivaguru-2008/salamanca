"""Typed domain errors and RFC 7807 ``application/problem+json`` mapping."""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = structlog.get_logger(__name__)

PROBLEM_CONTENT_TYPE = "application/problem+json"
_ERROR_TYPE_BASE = "https://fios.dev/errors"


class AppError(Exception):
    """Base class for typed application errors.

    Subclasses define the HTTP status, a stable error code (used in the
    problem ``type`` URI), and a human-readable title.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal-error"
    title: str = "Internal Server Error"

    def __init__(
        self,
        detail: str | None = None,
        *,
        headers: dict[str, str] | None = None,
        errors: list[dict[str, Any]] | None = None,
    ) -> None:
        self.detail = detail or self.title
        self.headers = headers or {}
        self.errors = errors
        super().__init__(self.detail)


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "bad-request"
    title = "Bad Request"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthorized"
    title = "Unauthorized"

    def __init__(self, detail: str | None = None, **kwargs: Any) -> None:
        super().__init__(detail, **kwargs)
        self.headers.setdefault("WWW-Authenticate", "Bearer")


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"
    title = "Forbidden"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "not-found"
    title = "Not Found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"
    title = "Conflict"


class PayloadTooLargeError(AppError):
    status_code = 413
    error_code = "payload-too-large"
    title = "Payload Too Large"


class UnsupportedMediaTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    error_code = "unsupported-media-type"
    title = "Unsupported Media Type"


class ValidationAppError(AppError):
    status_code = 422
    error_code = "validation-error"
    title = "Validation Error"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "rate-limited"
    title = "Too Many Requests"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "service-unavailable"
    title = "Service Unavailable"


class ProblemDetails(BaseModel):
    """RFC 7807 problem document (extended with correlation ids)."""

    model_config = ConfigDict(populate_by_name=True)

    type: str
    title: str
    status: int
    detail: str
    instance: str | None = None
    trace_id: str | None = None
    request_id: str | None = None
    errors: list[dict[str, Any]] | None = None


def _current_trace_id() -> str | None:
    from opentelemetry import trace

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        return format(ctx.trace_id, "032x")
    return None


def build_problem(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    title: str,
    detail: str,
    errors: list[dict[str, Any]] | None = None,
) -> ProblemDetails:
    return ProblemDetails(
        type=f"{_ERROR_TYPE_BASE}/{error_code}",
        title=title,
        status=status_code,
        detail=detail,
        instance=request.url.path,
        trace_id=_current_trace_id(),
        request_id=getattr(request.state, "request_id", None),
        errors=errors,
    )


def problem_response(
    request: Request,
    *,
    status_code: int,
    error_code: str,
    title: str,
    detail: str,
    headers: dict[str, str] | None = None,
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    problem = build_problem(
        request,
        status_code=status_code,
        error_code=error_code,
        title=title,
        detail=detail,
        errors=errors,
    )
    return JSONResponse(
        status_code=status_code,
        content=problem.model_dump(exclude_none=True),
        headers=headers,
        media_type=PROBLEM_CONTENT_TYPE,
    )


def _simplify_validation_errors(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    simplified: list[dict[str, Any]] = []
    for err in raw:
        loc = ".".join(str(part) for part in err.get("loc", ()))
        simplified.append(
            {
                "field": loc,
                "message": str(err.get("msg", "invalid value")),
                "type": str(err.get("type", "value_error")),
            }
        )
    return simplified


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)
    if exc.status_code >= 500:
        logger.error("app_error", error_code=exc.error_code, detail=exc.detail)
    return problem_response(
        request,
        status_code=exc.status_code,
        error_code=exc.error_code,
        title=exc.title,
        detail=exc.detail,
        headers=exc.headers or None,
        errors=exc.errors,
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    return problem_response(
        request,
        status_code=422,
        error_code="validation-error",
        title="Validation Error",
        detail="Request validation failed.",
        errors=_simplify_validation_errors(list(exc.errors())),
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return problem_response(
        request,
        status_code=exc.status_code,
        error_code="http-error",
        title=str(exc.detail) if exc.detail else "HTTP Error",
        detail=str(exc.detail) if exc.detail else "HTTP error.",
        headers=dict(exc.headers) if exc.headers else None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", exc_info=exc)
    return problem_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code="internal-error",
        title="Internal Server Error",
        detail="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
