# Smart Waste Collection Platform

WasteOps is evolving from an academic prototype into an API-backed waste collection operations platform.

- The public Streamlit entry page (`app.py`) is a branded product overview. It does not generate sample readings, train models at page load, or show simulated vehicle routes.
- The authenticated operations console is served from `web/index.html` and uses the FastAPI service for bins, telemetry, jobs, vehicles, dispatch and driver workflows.
- Set `WASTEOPS_CONSOLE_URL` in the Streamlit deployment to link the public entry page to the deployed operator console. Do not put API credentials in this variable.
- Operational records are not displayed on the public entry page. Sign-in and role checks remain in the API-backed console.

## Quick start (Docker)

1. Copy `.env.example` to `.env` and replace both secrets with unique, random values.
2. Run `docker compose up --build`.
3. Open `http://localhost:8000` for the operator console, `http://localhost:8000/driver.html` for the driver view, `http://localhost:8000/docs` for the interactive API and `http://localhost:8000/health` for the health check.

Never commit `.env` or expose bootstrap credentials in a public deployment. Production operator access uses named accounts and expiring, revocable sessions. Enroll individual devices from the administrator console; device credentials are returned once, hashed at rest, and scoped to one bin.

## Local API tests

```bash
cd backend
python -m venv .venv
# Activate the virtual environment, then:
pip install -r requirements.txt
API_TOKEN=test-operator-token pytest -q
```

The API defaults to a local SQLite database for development. Docker Compose configures PostgreSQL/PostGIS. The Render production container serves both `web/index.html` and `web/driver.html` from the same HTTPS origin as FastAPI, so browser session cookies remain same-site. Alembic migrations are applied automatically by the API container. Use a managed secret store before production.

## Optional ML model artifact

From the repository root, install `requirements.txt` and run `python person2_ml_prediction.py`. This trains a one-step-ahead model on the configured CSV and writes `models/waste_model.pkl`. The Compose stack mounts that directory read-only; rebuild/restart the API after training. The forecasts endpoint returns HTTP 503 when no artifact exists and skips bins without fresh temperature readings or enough history. The current model is not a validated 6/12-hour forecast. Keep `USE_MODEL_FOR_DISPATCH=false` until evaluation on representative field data supports enabling it.

## Operator identity and API flow

1. On a fresh database, create the first administrator once with `POST /api/v1/auth/bootstrap`, send `X-Bootstrap-Token: $API_TOKEN`, and provide a unique username plus a password of at least 12 characters. The bootstrap credential is never returned by the browser UI.
2. Sign in through `POST /api/v1/auth/login` with the username and password. The browser receives an eight-hour HttpOnly, SameSite=Strict session cookie (Secure in production); the token is never exposed to JavaScript or browser storage, and only its SHA-256 hash is stored server-side. Cookie-authenticated state-changing requests validate the Origin against the configured CORS allowlist. Keep the browser console and API on the same origin.
3. Administrators create named operator/admin accounts through `POST /api/v1/auth/users`, revoke accounts and all their sessions through `POST /api/v1/auth/users/{username}/revoke`, and inspect security events through `GET /api/v1/auth/audit`.
4. Create a bin using `POST /api/v1/bins` with an operator session. Enroll devices and drivers using administrator privileges; each credential is returned once, hashed at rest, and scoped to its bin or vehicle.
5. Send telemetry to `POST /api/v1/telemetry` using the device's `X-Device-Token`, then inspect readings using `GET /api/v1/bins/{bin_id}/history`.
6. Create collection candidates using `POST /api/v1/jobs`, approve eligible jobs, register vehicles, and dispatch selected jobs through `POST /api/v1/routes/dispatch`. The API obtains road-network costs, optimizes against registered capacities, persists the route plan, and records assignment events.

The old shared `API_TOKEN` is accepted as an operator credential only when `APP_ENV` is not `production`, to keep local development and existing test workflows simple. In production it is a one-time bootstrap secret only; it is not accepted on normal operator endpoints.

## Driver workflow and offline recovery

The driver page lists jobs assigned to the authenticated driver's vehicle and supports start, completion and exception transitions. The app shell and last-synced jobs are cached locally; offline actions are queued in IndexedDB and replayed with stable idempotency keys when the driver page is open/reopened online; OS-level Background Sync is not implemented. The queue stores action metadata, not the driver token. The driver token remains in tab-scoped session storage. Navigation is handed off to an external map application.

Driver transition requests accept an `Idempotency-Key` header. The database stores the key, driver/job/action identity, request fingerprint and original response. Replaying the exact request returns the original response without creating another service event; reusing a key with a changed payload or another job returns HTTP 409. A queued action that conflicts with the server's current job state remains blocked for driver/operator review rather than being silently discarded.

## Data truthfulness

Every bin has a `source` of `live`, `imported`, or `demo`. The operator interface only offers live and imported records, excludes demo-source bins from operational views, and the API rejects demo-source bin creation in production. Telemetry ingestion is authenticated and duplicate messages are idempotent by device and message ID. Routing uses real road-network distance/time data; if the provider fails, the API returns an error rather than fabricating distances. The API serves next-observation forecasts when a trained artifact and suitable telemetry are available; no field-performance claims are made. See [implementation status](docs/IMPLEMENTATION_STATUS.md) for remaining release blockers.

## Production configuration guardrails

Set `APP_ENV=production` to make the API refuse unsafe startup configuration. Production requires a non-SQLite durable database, a unique `API_TOKEN` of at least 32 characters for one-time initial-admin bootstrap, `AUTO_CREATE_SCHEMA=false`, `SEED_DEMO_DATA=false`, a trusted HTTPS routing provider, and explicit trusted HTTPS origins in `CORS_ORIGINS`. The deployment supports the authenticated HeiGIT openrouteservice v2 API (`ROUTING_PROVIDER=ors`, `ORS_BASE_URL=https://api.heigit.org/openrouteservice/v2`, secret `ORS_API_KEY`) as well as a trusted OSRM-compatible endpoint. The public OSRM demonstration server is rejected in production. Apply schema changes through Alembic migrations. Compose publishes database, API, and web ports on loopback by default and includes readiness/health checks; keep these binds local and terminate TLS at a properly configured reverse proxy. The guard prevents common misconfiguration; it is not a substitute for MFA/SSO decisions, trusted-proxy rate-limit configuration, managed secrets, backups, monitoring, and a security review.
