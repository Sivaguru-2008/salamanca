"""FastAPI application factory and lifecycle wiring."""

from __future__ import annotations

import functools
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.health import router as health_router
from app.api.middleware import (
    BodyLimitMiddleware,
    MetricsMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.api.openapi import SWAGGER_UI_PARAMETERS, install_openapi
from app.api.v1 import api_v1_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.health import HealthRegistry
from app.core.logging import configure_logging
from app.core.observability import setup_tracing, shutdown_tracing
from app.core.tasks import BackgroundTaskManager
from app.domain.auth.service import purge_stale_auth_sessions
from app.infra.db.session import build_engine, build_sessionmaker
from app.infra.redis.client import create_redis_client

logger = structlog.get_logger(__name__)

AUTH_SESSION_PURGE_INTERVAL_SECONDS = 3600.0


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

    engine = build_engine(settings)
    sessionmaker = build_sessionmaker(engine)
    app.state.db_engine = engine
    app.state.db_sessionmaker = sessionmaker

    # Tests may pre-install a redis client (e.g. fakeredis) before startup.
    owns_redis = getattr(app.state, "redis", None) is None
    if owns_redis:
        app.state.redis = create_redis_client(settings)

    tracer_provider = setup_tracing(app, engine, settings)

    health = HealthRegistry()

    async def check_database() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def check_redis() -> None:
        await app.state.redis.ping()

    health.register("postgres", check_database, critical=True)
    health.register("redis", check_redis, critical=True)
    app.state.health = health

    tasks = BackgroundTaskManager()
    tasks.add_periodic(
        "auth_session_purge",
        AUTH_SESSION_PURGE_INTERVAL_SECONDS,
        functools.partial(purge_stale_auth_sessions, sessionmaker, settings),
        jitter_seconds=60.0,
    )
    await tasks.start()
    app.state.tasks = tasks

    logger.info(
        "application_started",
        app=settings.app_name,
        version=settings.version,
        environment=settings.environment.value,
    )
    try:
        yield
    finally:
        await tasks.stop()
        if owns_redis:
            await app.state.redis.aclose()
        await engine.dispose()
        shutdown_tracing(tracer_provider)
        logger.info("application_stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    docs_enabled = settings.docs_enabled and not settings.is_production
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        debug=settings.debug,
    )
    app.state.settings = settings

    # Middleware registration is LIFO: the last one added runs first. Effective
    # order: RequestContext → CORS → SecurityHeaders → RateLimit → BodyLimit →
    # Metrics → router (per 06-api-security §1.2).
    app.add_middleware(MetricsMiddleware)
    app.add_middleware(BodyLimitMiddleware, settings=settings)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)

    app.include_router(health_router)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/metrics", tags=["ops"], summary="Prometheus metrics")
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    install_openapi(app, settings)
    return app


app = create_app()
