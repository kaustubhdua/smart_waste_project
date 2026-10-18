# Implementation status and honest limitations

## Added in this change

- FastAPI service with operator/device bearer-token gates.
- SQLAlchemy persistence for bins, telemetry, vehicles, collection jobs and service events.
- Validated telemetry ingestion with device/message idempotency.
- Collection job creation and explicit state-transition validation.
- OSRM road-route preview with real distance, duration and geometry; routing failure returns an error instead of inventing straight-line road distance.
- Docker Compose for PostgreSQL/PostGIS and the API.
- API tests and a basic health endpoint.

## Not yet production-complete

- The route preview uses the stop order supplied by the caller; it does **not** solve a vehicle-routing optimization problem. The existing OR-Tools implementation still needs integration with a road-distance matrix and persisted route plans.
- Authentication is a shared-token MVP, not multi-user identity, password login, OAuth, or granular per-role authorization. Rotate tokens and put the API behind TLS; do not expose demo tokens.
- ORM table creation is for development bootstrap. Production deployment must use Alembic migrations and a reviewed migration workflow.
- The public OSRM endpoint is a demonstration dependency with usage limits and no service guarantee. Production should use a self-hosted or contracted routing provider.
- The current ML model is not wired into this API, and no model performance claims are made. Add scheduled model artifacts, leakage-safe evaluation and a persistence baseline before using forecasts for operations.
- No physical sensor has been tested. Live telemetry requires a device to send authenticated, calibrated readings.
- The original Streamlit UI is not yet replaced by a production React driver/dispatcher experience.
- Tests have been authored but must be run in CI; a repository write is not evidence that tests passed.
