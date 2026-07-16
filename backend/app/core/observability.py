"""OpenTelemetry tracing setup: FastAPI, SQLAlchemy, and Redis instrumentation.

Tracing is controlled by ``FIOS_OTEL_ENABLED``. Spans are exported over
OTLP/HTTP when ``FIOS_OTEL_EXPORTER_ENDPOINT`` is configured; otherwise the
provider runs without an exporter (spans still enrich logs with trace ids).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.config import Settings

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = structlog.get_logger(__name__)

_EXCLUDED_URLS = "healthz,livez,readyz,metrics"


def setup_tracing(app: FastAPI, engine: AsyncEngine, settings: Settings) -> TracerProvider | None:
    if not settings.otel_enabled:
        return None

    resource = Resource.create(
        {
            SERVICE_NAME: settings.otel_service_name,
            SERVICE_VERSION: settings.version,
            "deployment.environment": settings.environment.value,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_exporter_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=f"{settings.otel_exporter_endpoint}/v1/traces")
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.redis import RedisInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=_EXCLUDED_URLS)
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine, tracer_provider=provider)
    RedisInstrumentor().instrument(tracer_provider=provider)

    logger.info(
        "tracing_enabled",
        service=settings.otel_service_name,
        exporter=settings.otel_exporter_endpoint or "none",
    )
    return provider


def shutdown_tracing(provider: TracerProvider | None) -> None:
    if provider is not None:
        provider.shutdown()
