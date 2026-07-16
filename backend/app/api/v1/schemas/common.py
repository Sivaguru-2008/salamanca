"""Shared response models."""

from __future__ import annotations

from pydantic import BaseModel

from app.core.errors import ProblemDetails
from app.core.pagination import Page

__all__ = ["HealthCheckReport", "HealthReport", "Message", "Page", "ProblemDetails"]


class Message(BaseModel):
    message: str


class HealthCheckReport(BaseModel):
    name: str
    healthy: bool
    latency_ms: float
    error: str | None = None
    critical: bool


class HealthReport(BaseModel):
    status: str
    version: str
    environment: str
    checks: list[HealthCheckReport] = []


PROBLEM_RESPONSES: dict[int | str, dict[str, object]] = {
    401: {"model": ProblemDetails, "description": "Not authenticated"},
    403: {"model": ProblemDetails, "description": "Insufficient permissions"},
    404: {"model": ProblemDetails, "description": "Resource not found"},
    409: {"model": ProblemDetails, "description": "Conflict"},
    422: {"model": ProblemDetails, "description": "Validation error"},
    429: {"model": ProblemDetails, "description": "Rate limited"},
}
