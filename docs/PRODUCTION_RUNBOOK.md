# Production deployment and operations runbook

This runbook is an operator checklist, not evidence that the project has already passed production acceptance. Record the environment, date, operator, evidence links and outcome for every drill.

## 1. Release boundary

Do not use this prototype for unsupervised municipal operations until all P0 gates in [the release checklist](RELEASE_CHECKLIST.md) have evidence. In particular, the current operator authentication is a shared bearer token, and the public OSRM endpoint is for development only.

## 2. Environment and secrets

- Use a dedicated production environment and a durable managed PostgreSQL/PostGIS database.
- Store `POSTGRES_PASSWORD` and `API_TOKEN` in a managed secret store; never commit `.env`, tokens, database URLs or device credentials.
- Use a unique operator token of at least 32 characters as a temporary deployment guardrail only; this does not replace identity-based authentication and role permissions.
- Set `APP_ENV=production`, `AUTO_CREATE_SCHEMA=false`, `SEED_DEMO_DATA=false`, explicit trusted HTTPS `CORS_ORIGINS`, and a contracted or self-hosted HTTPS routing provider in `OSRM_BASE_URL`.
- Keep database and application ports private. Terminate TLS at a maintained reverse proxy or managed ingress; configure security headers, request-size limits, timeouts and access logs.
- Use a staging environment to rehearse migrations and releases before production.

## 3. Release procedure

1. Identify the exact commit and release tag.
2. Confirm required CI workflows pass for that commit.
3. Build images from that commit and scan dependencies/images using the team's approved tools.
4. Back up the production database and confirm the backup completed.
5. Apply Alembic migrations using the documented deployment process. Do not enable automatic schema creation in production.
6. Deploy to staging first; verify readiness, authenticated API access, operator and driver workflows, routing-provider connectivity and log/alert delivery.
7. Promote the same immutable image artifacts to production.
8. Run smoke tests, monitor errors and latency, and record the release decision and rollback owner.

## 4. Backup and restore drill

Choose and record recovery objectives before operating the service:
- **RPO:** maximum acceptable amount of lost data.
- **RTO:** maximum acceptable restoration time.

At minimum, use managed automated backups or a scheduled encrypted PostgreSQL backup stored separately from the database host. Define retention and access permissions. Protect backups as sensitive data.

A restore drill must:
1. restore a recent backup into an isolated, non-production database;
2. apply only the migration steps appropriate to the recovery scenario;
3. verify expected tables and row counts for bins, telemetry, collection jobs, service events, route plans, vehicles, devices and drivers;
4. start the application against the restored database;
5. run readiness and API smoke tests, plus representative collection lifecycle checks;
6. record start/end time, data-loss window, discrepancies and corrective actions.

Do not claim disaster recovery is ready until this drill has passed and is repeated on a defined schedule.

## 5. Monitoring and incident response

Collect structured application logs and monitor:
- API availability, request volume, error rates and latency percentiles;
- database availability, connections, storage, slow queries and backup age;
- telemetry freshness, invalid readings, duplicate conflicts and device authentication failures;
- approved jobs awaiting dispatch, jobs stuck in progress, driver exceptions and route-provider failures;
- CPU, memory, disk, container restarts and certificate expiry.

Route alerts to an owned channel with an on-call contact and documented escalation. Never include bearer tokens, driver/device secrets, or sensitive payloads in logs.

For an incident: protect people and service continuity first; restrict access if compromise is suspected; preserve relevant logs; rotate/revoke affected credentials; restore from a known-good state if needed; document impact and follow-up actions.

## 6. Routing provider

Do not depend on the public demo OSRM endpoint for production. Configure a contracted service or self-hosted routing engine with an owner, capacity expectations, data refresh plan, availability target, timeout and retry policy. Test unreachable destinations and provider outage behavior. A route must not be dispatched if its constraints or route costs cannot be verified.

## 7. Sensor and field pilot

Before accepting readings as operational truth:
- document sensor model, firmware, installation geometry and calibration method;
- compare readings with manual measurements across empty, partially full and near-full states;
- test clock drift, intermittent connectivity, retries, duplicate delivery, stale readings, outliers and credential revocation;
- measure delivery success and fill-level error with sample size and confidence limitations;
- define how operators handle missing or implausible readings.

Start with a supervised pilot and retain a manual collection fallback. Do not infer cost savings or missed-collection reduction without a measured baseline and pilot results.

## 8. Rollback and post-release review

Document the last known-good image, compatible database schema, rollback owner and communication path before deployment. Prefer forward fixes for irreversible schema changes; database rollback must not be assumed safe. After release, review alerts, errors, dispatch outcomes and operator feedback, and update the release record.
