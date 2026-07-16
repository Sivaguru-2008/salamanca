"""FIOS operational CLI.

Usage: ``python -m app.cli --help`` (or the ``fios`` console script).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer

from app.core.config import get_settings
from app.core.rbac import Role

cli = typer.Typer(name="fios", help="FIOS backend operations.", no_args_is_help=True)
db_cli = typer.Typer(help="Database migrations.", no_args_is_help=True)
seed_cli = typer.Typer(help="Seed data.", no_args_is_help=True)
users_cli = typer.Typer(help="User management.", no_args_is_help=True)
openapi_cli = typer.Typer(help="OpenAPI schema tooling.", no_args_is_help=True)

cli.add_typer(db_cli, name="db")
cli.add_typer(seed_cli, name="seed")
cli.add_typer(users_cli, name="users")
cli.add_typer(openapi_cli, name="openapi")

_BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config():  # type: ignore[no-untyped-def]
    from alembic.config import Config

    config = Config(str(_BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_ROOT / "alembic"))
    return config


@cli.command()
def serve(
    host: str = typer.Option(None, help="Bind host (defaults to FIOS_HOST)."),
    port: int = typer.Option(None, help="Bind port (defaults to FIOS_PORT)."),
    reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes."),
) -> None:
    """Run the API with uvicorn."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=reload,
        log_config=None,
    )


@cli.command()
def routes() -> None:
    """List registered API routes."""
    from fastapi.routing import APIRoute

    from app.main import create_app

    app = create_app(get_settings())
    for route in sorted(app.routes, key=lambda r: getattr(r, "path", "")):
        if isinstance(route, APIRoute):
            methods = ",".join(sorted((route.methods or set()) - {"HEAD", "OPTIONS"}))
            typer.echo(f"{methods:10s} {route.path}")


@db_cli.command("upgrade")
def db_upgrade(revision: str = typer.Argument("head")) -> None:
    """Apply migrations up to REVISION (default: head)."""
    from alembic import command

    command.upgrade(_alembic_config(), revision)
    typer.echo(f"Upgraded to {revision}.")


@db_cli.command("downgrade")
def db_downgrade(revision: str = typer.Argument("-1")) -> None:
    """Revert migrations down to REVISION (default: one step)."""
    from alembic import command

    command.downgrade(_alembic_config(), revision)
    typer.echo(f"Downgraded to {revision}.")


@db_cli.command("revision")
def db_revision(message: str = typer.Option(..., "-m", "--message")) -> None:
    """Autogenerate a new migration."""
    from alembic import command

    command.revision(_alembic_config(), message=message, autogenerate=True)


@db_cli.command("current")
def db_current() -> None:
    """Show the current migration revision."""
    from alembic import command

    command.current(_alembic_config(), verbose=True)


@seed_cli.command("run")
def seed_run(
    only: list[str] = typer.Option(None, "--only", help="Run only the named seeder(s)."),
) -> None:
    """Run registered seeders (idempotent)."""

    async def _run() -> None:
        from app.infra.db.session import build_engine, build_sessionmaker, session_scope
        from app.infra.seed import run_seeders

        settings = get_settings()
        engine = build_engine(settings)
        try:
            async with session_scope(build_sessionmaker(engine)) as session:
                results = await run_seeders(session, settings, only=list(only) if only else None)
            for result in results:
                typer.echo(f"[{result.outcome:8s}] {result.seeder}: {result.detail}")
        finally:
            await engine.dispose()

    asyncio.run(_run())


@seed_cli.command("list")
def seed_list() -> None:
    """List registered seeders."""
    from app.infra.seed.framework import registered_seeders

    for cls in registered_seeders():
        typer.echo(f"{cls.order:4d}  {cls.name}")


@users_cli.command("create")
def users_create(
    email: str = typer.Option(..., "--email"),
    password: str = typer.Option(..., "--password", prompt=True, hide_input=True),
    role: Role = typer.Option(Role.OWNER, "--role"),
    full_name: str = typer.Option("", "--full-name"),
) -> None:
    """Create a user with the given role."""

    async def _run() -> None:
        from app.domain.users.service import UserService
        from app.infra.db.session import build_engine, build_sessionmaker, session_scope

        settings = get_settings()
        engine = build_engine(settings)
        try:
            async with session_scope(build_sessionmaker(engine)) as session:
                user = await UserService(session).register(
                    email=email,
                    password=password,
                    full_name=full_name,
                    role=role,
                    is_verified=True,
                )
                typer.echo(f"Created {user.role.value} {user.email} ({user.id})")
        finally:
            await engine.dispose()

    asyncio.run(_run())


@openapi_cli.command("export")
def openapi_export(
    out: Path = typer.Option(Path("openapi.json"), "--out", help="Output file path."),
) -> None:
    """Export the OpenAPI schema to a JSON file."""
    from app.main import create_app

    app = create_app(get_settings())
    out.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8")
    typer.echo(f"Wrote {out}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
