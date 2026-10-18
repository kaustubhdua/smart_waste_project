# Smart Waste Collection Platform — Engineering Upgrade

This repository is being evolved from a Streamlit/ML/routing prototype into a backend-backed waste collection platform. The original modules remain available; the new API foundation is under `backend/`.

## Quick start (Docker)

1. Copy `.env.example` to `.env` and replace both secrets with unique, random values.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/docs` for the interactive API and `http://localhost:8000/health` for the health check.

Never commit `.env` or expose operator tokens in a public deployment. Enroll individual devices from the operator API; device credentials are returned once, hashed at rest, and scoped to one bin.

## Local API tests

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
API_TOKEN=test-operator-token pytest -q
```

The API defaults to a local SQLite database for development. Docker Compose configures PostgreSQL/PostGIS. Alembic migrations are applied automatically by the API container. Use a managed secret store before production.

## Optional ML model artifact

From the repository root, install `requirements.txt` and run `python person2_ml_prediction.py`. This trains a one-step-ahead model on the configured CSV and writes `models/waste_model.pkl`. The Compose stack mounts that directory read-only; rebuild/restart the API after training. The forecasts endpoint returns HTTP 503 when no artifact exists and skips bins without fresh temperature readings or enough history. The current model is not a validated 6/12-hour forecast. Keep `USE_MODEL_FOR_DISPATCH=false` until evaluation on representative field data supports enabling it.

## API flow

1. Create a bin using `POST /api/v1/bins` with an operator bearer token.
2. Enroll a device with `POST /api/v1/devices`, then send telemetry to `POST /api/v1/telemetry` using the returned per-device `X-Device-Token`. Tokens can be rotated or revoked.
3. Inspect readings using `GET /api/v1/bins/{bin_id}/history`.
4. Create a collection candidate with `POST /api/v1/jobs`.
5. Move a job through validated transitions using `POST /api/v1/jobs/{job_id}/transitions`.
6. Approve eligible jobs, register vehicles, and dispatch selected jobs through `POST /api/v1/routes/dispatch`. This obtains OSRM road-network costs, optimizes against registered capacities, persists the route plan, and records vehicle assignment events.

## Data truthfulness

Every bin has a `source` of `live`, `imported`, or `demo`. Telemetry ingestion is authenticated and duplicate messages are idempotent by device and message ID. Routing uses real road-network distance/time data; if the provider fails, the API returns an error rather than fabricating distances. The API serves next-observation forecasts when a trained artifact and suitable telemetry are available; no field-performance claims are made. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for remaining release blockers.

## Production configuration guardrails

Set `APP_ENV=production` to make the API refuse unsafe startup configuration. Production requires a non-SQLite durable database, an `API_TOKEN` with at least 32 characters, `AUTO_CREATE_SCHEMA=false`, `SEED_DEMO_DATA=false`, and explicit trusted HTTPS origins in `CORS_ORIGINS`. Apply schema changes through Alembic migrations. The guard prevents common misconfiguration; it is not a substitute for identity-based RBAC, TLS termination, managed secrets, backups, monitoring, and a security review.
