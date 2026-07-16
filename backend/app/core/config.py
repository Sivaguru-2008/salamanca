"""Application configuration.

Settings are loaded from environment variables (prefix ``FIOS_``) layered over
``.env`` and an optional environment-specific ``.env.<environment>`` file, the
latter taking precedence. Access settings through :func:`get_settings`.
"""

from __future__ import annotations

import os
from datetime import timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_INSECURE_SECRETS = frozenset(
    {
        "",
        "change-me",
        "changeme",
        "secret",
        "local-dev-only-secret-change-me",
    }
)


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class JWTAlgorithm(StrEnum):
    HS256 = "HS256"
    RS256 = "RS256"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FIOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "FIOS API"
    version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_v1_prefix: str = "/api/v1"
    host: str = "0.0.0.0"
    port: int = 8000
    docs_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    log_json: bool = True

    # Database
    database_url: str | None = None
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "fios"
    postgres_password: str = "fios"
    postgres_db: str = "fios"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    # Redis
    redis_url: str | None = None
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_max_connections: int = 50

    # Auth / JWT
    jwt_algorithm: JWTAlgorithm = JWTAlgorithm.HS256
    jwt_secret_key: str = "local-dev-only-secret-change-me"
    jwt_private_key_path: str | None = None
    jwt_public_key_path: str | None = None
    jwt_issuer: str = "fios"
    jwt_audience: str = "fios-api"
    access_token_ttl_seconds: int = Field(default=900, ge=60)
    refresh_token_ttl_seconds: int = Field(default=30 * 24 * 3600, ge=3600)
    auth_session_retention_days: int = Field(default=7, ge=1)

    # CORS
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )
    cors_allow_credentials: bool = True

    # Rate limiting
    rate_limit_enabled: bool = True
    rate_limit_requests: int = Field(default=120, ge=1)
    rate_limit_window_seconds: int = Field(default=60, ge=1)

    # Request validation
    max_request_body_bytes: int = Field(default=10 * 1024 * 1024, ge=1024)

    # OpenTelemetry
    otel_enabled: bool = False
    otel_exporter_endpoint: str | None = None
    otel_service_name: str = "fios-api"

    # LLM providers (AI council / loan analysis). Gemini is preferred when
    # both keys are configured; Groq is used as fallback.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: float = Field(default=45.0, gt=0)
    chat_history_max_messages: int = Field(default=20, ge=2)
    chat_history_ttl_seconds: int = Field(default=7 * 24 * 3600, ge=60)

    # Document uploads
    upload_dir: str = "uploads"
    max_upload_bytes: int = Field(default=15 * 1024 * 1024, ge=1024)

    # Seeds
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("log_level")
    @classmethod
    def _normalize_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"invalid log level: {value}")
        return level

    @model_validator(mode="after")
    def _validate_security(self) -> Settings:
        if self.jwt_algorithm is JWTAlgorithm.RS256:
            if not self.jwt_private_key_path or not self.jwt_public_key_path:
                raise ValueError(
                    "RS256 requires FIOS_JWT_PRIVATE_KEY_PATH and FIOS_JWT_PUBLIC_KEY_PATH"
                )
        elif self.is_production and self.jwt_secret_key.lower() in _INSECURE_SECRETS:
            raise ValueError("FIOS_JWT_SECRET_KEY must be set to a strong value in production")
        return self

    def access_token_ttl_delta(self) -> timedelta:
        return timedelta(seconds=self.access_token_ttl_seconds)

    def refresh_token_ttl_delta(self) -> timedelta:
        return timedelta(seconds=self.refresh_token_ttl_seconds)

    @property
    def is_production(self) -> bool:
        return self.environment is Environment.PRODUCTION

    @property
    def is_testing(self) -> bool:
        return self.environment is Environment.TESTING

    @property
    def sqlalchemy_database_uri(self) -> str:
        if self.database_url:
            return self.database_url
        if self.environment in (Environment.DEVELOPMENT, Environment.TESTING):
            if not os.getenv("FIOS_DATABASE_URL") and not os.getenv("FIOS_POSTGRES_HOST"):
                return "sqlite+aiosqlite:///salamanca.db"
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        if self.redis_url:
            return self.redis_url
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"


def _env_files() -> tuple[str, ...]:
    """Env-file chain: ``.env`` plus ``.env.<environment>`` (higher precedence)."""
    files: list[str] = [".env"]
    env = os.getenv("FIOS_ENVIRONMENT", "").strip().lower()
    if env:
        files.append(f".env.{env}")
    return tuple(files)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(_env_file=_env_files())
