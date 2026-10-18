# Implementation status and honest limitations

## Implemented in this branch
- FastAPI service with separate operator/device shared-token gates.
- SQLAlchemy persistence for bins, telemetry, collection jobs, vehicles and service events.
- Validated telemetry ingestion with idempotency for duplicate device messages.
- Explicit collection-job state transitions and service-event history.
- OSRM road distance/time matrix and route geometry integration.
- OR-Tools capacitated vehicle routing over the OSRM road-distance matrix.
- Docker Compose for PostgreSQL/PostGIS and the API, environment template, API/optimizer tests and CI workflow.

## Still required before production
- Route plans are returned but not yet persisted as versioned route/stop records; add route plan tables and transactional assignment to vehicles/jobs.
- Authentication is a shared-token MVP, not multi-user identity, password login, OAuth or granular RBAC. Rotate tokens and put the API behind TLS; do not expose demo tokens.
- ORM table creation is for development bootstrap. Production deployment must use Alembic migrations and a reviewed migration workflow.
- The public OSRM endpoint is a demonstration dependency with usage limits and no service guarantee. Production should use a self-hosted or contracted routing provider.
- The existing ML model is not wired into the API. Add versioned artifacts, scheduled predictions, leakage-safe evaluation and persistence/seasonal baselines before using forecasts operationally.
- The existing Streamlit UI is not yet connected to this API or replaced by a driver/dispatcher experience.
- No physical sensor has been tested. Live telemetry requires a device to send authenticated, calibrated readings.
- Tests must pass in CI; a repository write is not evidence that tests passed.
