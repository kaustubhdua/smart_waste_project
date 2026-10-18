# Smart Waste Collection & Fleet Optimization

<p align="center"><strong>Observe → forecast → prioritize → optimize → collect</strong></p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white">
  <img alt="Routing" src="https://img.shields.io/badge/Routing-OR--Tools-4285F4">
  <img alt="Database" src="https://img.shields.io/badge/Database-PostgreSQL%20%2B%20PostGIS-4169E1?logo=postgresql&logoColor=white">
  <img alt="Status" src="https://img.shields.io/badge/Status-Engineering%20prototype-orange">
</p>

A waste-collection engineering project combining time-series feature engineering, fill-level prediction, collection-priority scoring, capacity-constrained vehicle routing, telemetry ingestion, persistent service history, and a map-based operator console.

> **Honest status:** this is an engineering prototype, not a proven municipal deployment. Synthetic/demo records are not live sensor readings. Hardware calibration, identity-based role permissions, field evaluation, and production operations still require real-world validation.

## Two ways to run it

### 1. Full-stack API + operator console

The platform foundation lives in the backend and web directories. It includes FastAPI, PostgreSQL/PostGIS, telemetry persistence, job lifecycle events, OSRM road-network costs, OR-Tools route optimization, Alembic schema migrations, and an API-connected operator console.

1. Copy .env.example to .env.
2. Replace both placeholder secrets with unique random values.
3. Start the services:

    docker compose up --build

4. Open the operator console at http://localhost:8080, API docs at http://localhost:8000/docs, and health check at http://localhost:8000/health.

Enter the configured API_TOKEN in the operator console. Enroll each device through POST /api/v1/devices. Store the returned X-Device-Token securely; only its hash is persisted. Send readings to POST /api/v1/telemetry with the enrolled device_id, its bound bin_id, a unique message_id, calibrated fill_percent, and a timezone-aware ISO timestamp. Device credentials can be rotated or revoked. The UI does not invent missing telemetry.

Route optimization uses the OSRM road-distance matrix and OR-Tools capacity constraints. The public OSRM endpoint is only suitable for development; use a contracted or self-hosted routing provider for a deployed service.

### 2. Legacy Streamlit / ML demonstration

Install the pinned root requirements and launch:

    python -m venv .venv
    # Activate the environment
    pip install -r requirements.txt
    streamlit run app.py

The Streamlit route solver remains a legacy demonstration that uses approximate coordinate costs; the backend route optimizer is the road-network implementation. The ML model is trained separately using python person2_ml_prediction.py or from the dashboard control. Its target is the next observed fill value, not a validated six- or twelve-hour forecast.

## Architecture

    Operator console (web/) ──┐
                              ├── FastAPI ── PostgreSQL / PostGIS
    IoT device ── HTTPS API ──┘       │
                                      ├── Telemetry and service history
                                      ├── OSRM road matrix / route geometry
                                      └── OR-Tools CVRP optimizer

    CSV / synthetic demonstration data ── feature engineering ── Random Forest
                                                               └── MAE/RMSE baselines

## Main capabilities

- **Telemetry:** validated readings, device token gate, and duplicate-message idempotency.
- **Data integrity:** persistent bins, collection jobs, service events, route plans, and schema migration.
- **Prediction:** trained model artifact, inference helper, chronological holdout, mean baseline and last-observation baseline.
- **Priority:** deterministic bounded weighted heuristic. It is not mislabeled as a true fuzzy-inference engine.
- **Routing:** OSRM road-distance matrix, OR-Tools CVRP capacity constraints, route geometry and persisted route-plan history.
- **Operator UI:** responsive bin register/list, telemetry summary, map and route optimization controls.
- **CI:** legacy Python tests and backend API/optimizer tests.

## Tests

    # Existing Python core
    pip install -r requirements.txt
    python -m unittest discover -s tests -v

    # API and routing optimizer
    cd backend
    pip install -r requirements.txt
    PYTHONPATH=. API_TOKEN=test-operator-token DEVICE_TOKEN=test-device-token pytest -q

## API overview

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /api/v1/bins | Register a bin |
| GET | /api/v1/bins | List active bins |
| POST | /api/v1/devices | Enroll a device and issue its one-time token |
| GET | /api/v1/devices | List device status without revealing tokens |
| POST | /api/v1/devices/{device_id}/rotate-token | Rotate a device credential |
| POST | /api/v1/drivers | Enroll a driver and issue a one-time token |
| GET | /api/v1/driver/jobs | List stops for the authenticated driver vehicle |
| POST | /api/v1/driver/jobs/{job_id}/transition | Start, complete or report an assigned stop exception |
| DELETE | /api/v1/devices/{device_id} | Revoke a device credential |
| POST | /api/v1/telemetry | Ingest a live device reading |\n| POST | /api/v1/telemetry/import-csv | Import validated historical telemetry CSV (2 MB / 10,000 row limit) |
| GET | /api/v1/bins/{bin_id}/history | Inspect stored readings |\n| GET | /api/v1/operations/summary | Inspect freshness and job-state counts |\n| GET | /api/v1/jobs | List collection jobs, optionally filtered by status |\n| GET | /api/v1/jobs/{job_id}/events | Inspect service history |\n| POST | /api/v1/vehicles | Register a collection vehicle |\n| POST | /api/v1/jobs/{job_id}/assign | Assign a job to a capacity-checked vehicle |
| POST | /api/v1/jobs | Create a collection candidate |
| POST | /api/v1/jobs/{job_id}/transitions | Record a validated lifecycle transition |
| POST | /api/v1/routes/optimize | Preview an optimized route plan |\n| POST | /api/v1/routes/dispatch | Optimize approved jobs against registered vehicles and assign stops transactionally |
| GET | /api/v1/routes/plans | List persisted route plans |\n| GET | /health/ready | Check database readiness |
| GET | /api/v1/routes/plans/{plan_id} | Retrieve a route plan |

## Limitations and next production gates

- Shared bearer tokens are a development authentication mechanism, not multi-user login or role-based authorization.
- The public OSRM endpoint has usage limits and no production service guarantee.
- Route plans are persisted, but assignment to named drivers and vehicles is not yet a complete dispatch workflow.
- The ML pipeline has not been validated against real sensor data and is not yet served by the API.
- No physical sensor, calibration process, municipal pilot, or real operational savings claim has been validated.
- Use production-grade secret management, TLS, backups, monitoring, threat modeling, and a reviewed migration process before exposing the service publicly.

See [implementation status](docs/IMPLEMENTATION_STATUS.md) and README_PLATFORM.md for details.
