"""OpenAPI / Swagger customization."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from app.core.config import Settings

TAGS_METADATA = [
    {"name": "auth", "description": "Registration, login, token rotation, logout."},
    {"name": "users", "description": "Profiles and administrative user management."},
    {"name": "ops", "description": "Liveness/readiness probes and operational endpoints."},
]

API_DESCRIPTION = (
    "Financial Intelligence Operating System — backend platform API.\n\n"
    "Errors follow RFC 7807 (`application/problem+json`). List endpoints use "
    "cursor pagination (`?cursor=&limit=`) with `filter=field:op:value` and "
    "`sort=-field` conventions. Authenticate with `Authorization: Bearer <access token>`."
)

SWAGGER_UI_PARAMETERS = {
    "persistAuthorization": True,
    "displayRequestDuration": True,
    "docExpansion": "none",
    "filter": True,
    "tryItOutEnabled": True,
}


def install_openapi(app: FastAPI, settings: Settings) -> None:
    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=settings.app_name,
            version=settings.version,
            description=API_DESCRIPTION,
            routes=app.routes,
            tags=TAGS_METADATA,
            servers=[{"url": "/", "description": "Current host"}],
            contact={"name": "FIOS Platform Team"},
            license_info={"name": "Proprietary"},
        )
        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {})["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Paste an access token from POST /api/v1/auth/login.",
        }
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
