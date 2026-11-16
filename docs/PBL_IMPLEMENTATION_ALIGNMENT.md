# PBL implementation and deployment alignment

Review date: 16 November 2026  
Repository: `kaustubhdua/smart_waste_project`

## Supported product entry points

The primary product is the API-backed browser application:

- `web/index.html` and `web/operator.js`: authenticated operator console.
- `web/driver.html` and `web/driver.js`: vehicle-scoped driver workspace and offline action queue.
- `backend/app/main.py`: FastAPI application and operational API.
- PostgreSQL/PostGIS, Alembic migrations and Docker Compose provide persistence and local deployment.

The standalone root `app.py` Streamlit workspace remains available as a separate lightweight planning application. It has session-scoped state and is not connected to the API-backed platform.

## Training workspace

Set `SEED_DEMO_DATA=true` in a non-production environment to opt into the idempotent training seed. The API container runs the seed after migrations. The seed creates 16 collection points, four vehicles, six hourly telemetry observations per point, four driver identities, two assigned jobs and additional detected jobs. Driver tokens are random, stored as hashes and printed once when each training driver is created.

The operator console now includes records whose internal source is `demo`, rather than filtering them out. Row-level source labels are omitted to keep the operational UI clean; the header's **Training workspace** indicator provides the environment disclosure. The generated values must not be represented as physical sensor readings or verified municipal operations.

## Algorithms and interpretation

The API-backed application uses the shared zero-order Sugeno fuzzy inference engine for collection urgency and Google OR-Tools for capacity-constrained optimization. Route optimization uses a road-routing provider for distance matrices and route geometry. The provider must be configured and reachable; public OSRM is only a development dependency.

The optional Random Forest artifact path supports next-observation inference when a compatible artifact and sufficient recent telemetry exist. Model-assisted dispatch remains disabled by default. Do not describe this as a calibrated 6/12-hour forecast.

The standalone Streamlit workspace has its own separate routing implementation and uses coordinate-derived estimates, not road-network distances.

## Verification boundaries

The repository contains API, authentication, configuration, routing, optimizer, Python, browser and accessibility tests, plus CI workflows for container and Compose checks. These checks must be run on the exact candidate commit. This document does not claim that a new workflow run has passed.

The training environment exercises real database writes and workflow transitions over generated data. It does not prove hardware calibration, production load, predictive quality, live routing service guarantees or real-world collection savings. Production still requires the gates documented in `docs/IMPLEMENTATION_STATUS.md` and `docs/DEPLOYMENT_RUNBOOK.md`.
