# Smart Waste Collection Platform — Engineering Upgrade

This repository is being evolved from a Streamlit/ML/routing prototype into a backend-backed waste collection platform. The original modules remain available; the new API foundation is under `backend/`.

## Quick start (Docker)

1. Copy `.env.example` to `.env` and replace all three secrets with unique, random values.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000/docs` for the interactive API and `http://localhost:8000/health` for the health check.

Never commit `.env` or expose shared tokens in a public deployment.

## Local API tests

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
API_TOKEN=test-operator-token DEVICE_TOKEN=test-device-token pytest -q
```

The API defaults to a local SQLite database for development. Docker Compose configures PostgreSQL/PostGIS. Before production, add Alembic migrations and a managed secret store.

## API flow

1. Create a bin using `POST /api/v1/bins` with an operator bearer token.
2. Send device telemetry to `POST /api/v1/telemetry` with `X-Device-Token`.
3. Inspect readings using `GET /api/v1/bins/{bin_id}/history`.
4. Create a collection candidate with `POST /api/v1/jobs`.
5. Move a job through validated transitions using `POST /api/v1/jobs/{job_id}/transitions`.
6. Request a road-route preview using `POST /api/v1/routes/preview`. This obtains road distance/time/geometry from OSRM and deliberately fails if routing is unavailable. It does not claim to optimize stop order.

## Data truthfulness

Every bin has a `source` of `live`, `imported`, or `demo`. Telemetry ingestion is authenticated and duplicate messages are idempotent by device and message ID. The route preview is road-based, but caller-supplied stop ordering is not a vehicle-routing solution. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for remaining release blockers.

## Original application

The original Streamlit app and ML/OR-Tools modules remain in place. They should only be described as production-ready after model serving, leakage-safe evaluation, road-matrix optimization, frontend integration, migrations, user/role identity, end-to-end tests and a real-data pilot are complete.
