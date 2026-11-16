# WasteOps — API-backed training and operations platform

The primary product experience is the browser-based operator console and driver workspace backed by FastAPI and PostgreSQL/PostGIS. The root Streamlit application remains available as a lightweight, standalone planning workspace; it is not connected to the API-backed platform.

## Start a populated training environment

Requirements: Docker Compose v2.

1. Copy `.env.example` to `.env`.
2. Set unique local values for `POSTGRES_PASSWORD` and `API_TOKEN`.
3. Set `SEED_DEMO_DATA=true` in `.env`. This is an explicit non-production choice; the backend refuses demo seeding in production.
4. Start the stack:

```bash
docker compose up --build -d
```

5. Open [http://localhost:8080](http://localhost:8080) for the operator console and [http://localhost:8080/driver.html](http://localhost:8080/driver.html) for the driver workspace.
6. Create the initial administrator once with `POST /api/v1/auth/bootstrap`, sending the `API_TOKEN` from `.env` in the `X-Bootstrap-Token` header and a username plus password of at least 12 characters in the JSON body. Then sign in through the operator console. Create named operator and driver accounts through the supported credential-management workflows.

The training seed is idempotent. It creates a small service area, collection points, fleet vehicles and timestamped telemetry history. The operator console includes these records in its normal tables, map, priority and dispatch workflows. The interface uses a compact **Training workspace** indicator rather than repeating provenance labels on every row. The indicator is intentional: generated records must not be mistaken for readings from calibrated physical devices.

To run without generated records, set `SEED_DEMO_DATA=false` and start with a fresh database volume. To reset a local training environment, stop the stack and remove its local database volume only when you are comfortable losing all workspace data:

```bash
docker compose down -v
docker compose up --build -d
```

## What the platform exercises

- Persistent bin, vehicle, telemetry, job, route-plan and service-event records.
- Operator bootstrap, named accounts, role-aware access, session revocation and audit events.
- Device-scoped telemetry ingestion, message idempotency, timestamp/freshness validation and historical CSV import.
- Sugeno fuzzy collection urgency and capacity-constrained route optimization using a road-routing provider.
- Approval, dispatch, driver stop workflows, completion/exception handling and vehicle release.
- Driver offline cache and idempotent queued actions while the driver workspace is open or reopened.
- Optional next-observation model inference when a compatible, versioned artifact and sufficient recent telemetry are available.

## Verify

```bash
docker compose ps
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/health/ready
```

Run backend tests from the repository root using the backend environment described in `backend/requirements.txt`, then run the root Python tests using `requirements.txt`. GitHub Actions also contains API, browser and Compose validation workflows.

## Important boundaries

The training environment exercises real application code, database writes, optimization and workflow transitions. Its preloaded records are generated examples, not physical sensor readings or verified municipal service events. The model is a next-observation estimator, not a calibrated long-horizon forecast. Public OSRM is a development routing dependency and has no service guarantee. Production still requires calibrated hardware, representative field validation, managed secrets, HTTPS ingress, durable backups, monitoring, load/security/accessibility review and a controlled municipal pilot.

See `docs/IMPLEMENTATION_STATUS.md`, `docs/DEPLOYMENT_RUNBOOK.md` and `docs/RELEASE_CHECKLIST.md` for implementation boundaries and release gates.
