# Implementation status and honest limitations

## Implemented in this branch
- FastAPI API with shared operator bearer token and individually enrolled device/driver tokens; device and driver tokens are stored as SHA-256 hashes, can be rotated/revoked, and are scoped to a bin or vehicle.
- PostgreSQL/PostGIS Docker Compose environment, SQLAlchemy persistence, Alembic migrations and database readiness check.
- Bin registry, vehicle registry, telemetry history, collection jobs, service events, route plans and operations summary.
- Live telemetry ingestion with timezone validation, future-clock-skew rejection, configurable freshness checks, idempotent message handling and bin-scoped device authorization.
- Historical telemetry CSV import with required-column validation, upload and row limits, deduplication, batch commit and explicit imported source labels.
- Model artifact loading and an API endpoint for next-observation fill predictions when enough recent readings and temperature values are available.
- Optional model-assisted collection demand, disabled by default; priority uses a clearly documented weighted heuristic and real service-history timing when available.
- OSRM road-distance matrix and geometry plus OR-Tools capacity-constrained optimization. The dispatch endpoint optimizes approved jobs against registered vehicles, persists the route plan, and assigns stops with service events transactionally.
- Online driver view with vehicle-scoped jobs, external navigation handoff, start/complete/exception actions and driver credential enrollment.
- Operator console for bins, device enrollment, vehicles, jobs, approval, route dispatch and optional model forecasts.
- Explicitly labeled demo seed data for local development; CI verifies that seeding is idempotent.
- Pinned dependencies, backend API/optimizer tests, original Python tests, migration checks, browser JavaScript syntax checks and Docker image build validation.

## Still required before production
- Operator authentication is a shared bearer-token MVP, not multi-user identity, OAuth or granular RBAC. Add managed identity, per-user roles, rate limiting and secret rotation policies.
- Public OSRM is a development dependency with usage limits and no service guarantee; use a contracted or self-hosted routing service for deployment.
- The model predicts the next observed fill value; it is not a calibrated 6/12-hour forecast. Its current evaluation is based on the repository dataset and does not establish field accuracy. Temperature readings and roughly hourly recent observations are required.
- Model-assisted demand is disabled by default. Do not enable USE_MODEL_FOR_DISPATCH until model evaluation on representative real sensor data supports the change.
- No physical sensor has been calibrated or field-tested. Device clock synchronization, sensor mounting, bin geometry and real fill measurement need a pilot.
- Driver view is online-only, with no offline action queue or embedded turn-by-turn navigation; navigation is handed off to an external map application.
- Although PostGIS is included in the database image, the current core schema stores latitude/longitude as validated numeric columns rather than using spatial column/index features.
- Production backups/restore drills, TLS, managed secrets, observability/alerting, load tests, accessibility review and a municipal field pilot remain release gates.
- CI passing proves the checked code and container builds work in the test environment; it does not prove hardware calibration, production load, predictive quality or real-world savings.