# Implementation status and honest limitations

## Implemented in this branch
- FastAPI service with separate operator/device shared-token gates.
- SQLAlchemy persistence for bins, telemetry, collection jobs, vehicles, route plans and service events.
- Validated telemetry ingestion with duplicate-message idempotency; reused message IDs with changed payloads return conflict.
- Timezone-aware telemetry timestamps, future-clock-skew rejection and configurable freshness checks for demand estimation and route planning.
- Operations summary for telemetry freshness, bin counts, active vehicles and job-state counts.
- Collection job listing, service-event history, explicit state transitions and capacity-checked vehicle assignment.\n- Dispatch endpoint optimizes approved jobs against registered vehicle capacities, persists the route plan, and assigns each job with an audit event in one database transaction.\n- Database readiness probe and placeholder-token rejection.
- OSRM road distance/time matrix and route geometry integration.
- OR-Tools capacitated vehicle routing over road-network distances with finite input validation.
- Route optimization results persisted as route-plan records and retrievable from history.
- Alembic initial schema migration.
- Model training separated from dashboard startup, model artifact loading/inference, and mean/persistence baseline metrics.
- Priority engine accurately described as a deterministic weighted heuristic; service time is not fabricated when collection history is absent.
- Responsive operator console served by Nginx, connected to API bin records, telemetry history and route optimization.
- Docker Compose for PostgreSQL/PostGIS, API and web console; environment template, tests and CI workflows.

## Still required before production
- Authentication is a shared-token MVP, not multi-user identity, password login, OAuth or granular RBAC. Rotate tokens and put the API behind TLS; do not expose demo tokens.
- The device token is currently shared across devices. Per-device enrollment, revocation, token rotation and device-to-bin authorization are required before fleet rollout.
- The public OSRM endpoint is a demonstration dependency with usage limits and no service guarantee. Production should use a self-hosted or contracted routing provider.
- The ML model is one-step-ahead and currently trained on the CSV dataset. It is not a calibrated 6/12-hour field forecast and is not yet served by the API.
- No physical sensor has been tested. Live telemetry requires a device to send authenticated, calibrated readings.
- The web console is an operator prototype, not a full offline-capable driver PWA; user/role identity and audit review still need hardening.
- CI verifies code and migrations, but does not prove hardware calibration, production load, field accuracy or real-world savings.
