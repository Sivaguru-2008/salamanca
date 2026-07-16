# FIOS — Backend Foundation

Backend platform foundation for the Financial Intelligence Operating System.
Architecture reference: [docs/architecture](docs/architecture/README.md).

## Run the stack (Docker)

```bash
docker compose up --build -d
```

| Service  | URL                          | Credentials                          |
|----------|------------------------------|--------------------------------------|
| API      | http://localhost:8000        | —                                    |
| Swagger  | http://localhost:8000/docs   | —                                    |
| PgAdmin  | http://localhost:5050        | admin@fios.com / admin-fios-local  |
| Postgres | localhost:5432               | fios / fios                          |
| Redis    | localhost:6379               | —                                    |

Migrations run automatically before the API starts. Seed an admin user:

```bash
docker compose exec api python -m app.cli seed run
```

## Local development (without Docker for the app)

Requires Python 3.12 and running Postgres + Redis (`docker compose up -d postgres redis`).

```bash
cd backend
cp .env.example .env
pip install -r requirements.txt -r requirements-dev.txt
alembic upgrade head
python -m app.cli serve --reload
```

## Quality gates

```bash
make lint   # ruff + black --check
make type   # mypy
make test   # pytest (self-contained: sqlite + fakeredis, no services needed)
```

## CLI

```bash
cd backend
python -m app.cli --help          # serve | db | seed | users | openapi | routes
python -m app.cli users create --email you@example.com --password secret123 --role admin
```

## Health & observability

- `GET /healthz` — liveness
- `GET /livez` — liveness alias
- `GET /readyz` — readiness (checks Postgres + Redis)
- `GET /metrics` — Prometheus metrics
- Set `FIOS_OTEL_ENABLED=true` and `FIOS_OTEL_EXPORTER_ENDPOINT=http://collector:4318` for OTLP traces.
