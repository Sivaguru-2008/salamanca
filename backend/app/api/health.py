"""Operational endpoints: liveness, readiness."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.api.v1.schemas.common import HealthCheckReport, HealthReport
from app.core.health import HealthRegistry

router = APIRouter(tags=["ops"], include_in_schema=True)


def _base_report(request: Request, status_text: str) -> HealthReport:
    settings = request.app.state.settings
    return HealthReport(
        status=status_text,
        version=settings.version,
        environment=settings.environment.value,
    )


@router.get("/healthz", response_model=HealthReport, summary="Liveness probe")
async def healthz(request: Request) -> HealthReport:
    return _base_report(request, "ok")


@router.get("/livez", response_model=HealthReport, summary="Liveness probe (alias)")
async def livez(request: Request) -> HealthReport:
    return _base_report(request, "ok")


@router.get(
    "/readyz",
    response_model=HealthReport,
    summary="Readiness probe (checks Postgres and Redis)",
    responses={503: {"model": HealthReport, "description": "One or more dependencies down"}},
)
async def readyz(request: Request, response: Response) -> HealthReport:
    registry: HealthRegistry = request.app.state.health
    ready, results = await registry.run_all()

    report = _base_report(request, "ok" if ready else "degraded")
    report.checks = [
        HealthCheckReport(
            name=r.name,
            healthy=r.healthy,
            latency_ms=r.latency_ms,
            error=r.error,
            critical=r.critical,
        )
        for r in results
    ]
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
