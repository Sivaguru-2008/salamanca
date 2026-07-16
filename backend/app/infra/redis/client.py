"""Async Redis client factory."""

from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import Settings


def create_redis_client(settings: Settings) -> Redis:
    return Redis.from_url(
        settings.redis_dsn,
        encoding="utf-8",
        decode_responses=True,
        max_connections=settings.redis_max_connections,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )
