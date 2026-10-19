# Deployment and operations runbook

This runbook is a controlled checklist, not evidence that a production environment exists. Do not mark a gate complete until a deployment record or test artifact is linked.

## Deployment model

Recommended topology:

- Public HTTPS reverse proxy / managed ingress
- Private API service; only the proxy can reach it
- Private PostgreSQL/PostGIS instance with TLS where supported
- Managed secret store for operator and database credentials
- Persistent, encrypted backups in a separate failure domain
- Centralized logs, metrics, uptime checks, and alert routing
- A separate staging environment using synthetic data

The Compose stack is a local/demo deployment. Published ports bind to loopback by default. Do not expose the database or raw API port directly to the public internet. Configure TLS, proxy headers, request limits, and secure headers in the chosen hosting platform.

## Required configuration before production

Set these through the hosting platform's secret/configuration manager, not a committed `.env` file:

- `APP_ENV=production`
- `DATABASE_URL`: durable PostgreSQL connection string
- `API_TOKEN`: unique random secret of at least 32 characters (temporary MVP credential only; this does not replace per-user identity)
- `AUTO_CREATE_SCHEMA=false`
- `SEED_DEMO_DATA=false`
- `CORS_ORIGINS`: exact HTTPS origins, no wildcard
- `OSRM_BASE_URL`: contracted or self-hosted HTTPS routing service, not a public demo endpoint
- `MODEL_PATH`: an explicitly versioned artifact path if forecasts are enabled
- `USE_MODEL_FOR_DISPATCH=false` until representative evaluation approves otherwise

The API's startup guard checks several unsafe settings. It does not verify secret-manager quality, network isolation, certificate renewal, database backup, identity/RBAC, or hosting security.

## Release procedure

1. Review the diff, dependency changes, migration scripts, and release checklist.
2. Require all applicable CI jobs to pass on the exact candidate commit.
3. Build immutable API and web image tags from that commit; record image digests.
4. Deploy to staging with production-like configuration and synthetic data.
5. Apply Alembic migrations using a dedicated migration step; take a pre-migration backup for changes that could affect data.
6. Run smoke checks:
   - `GET /health` returns 200.
   - `GET /health/ready` returns 200 only when the database is reachable.
   - Operator and driver pages load over HTTPS.
   - Unauthorized requests are rejected.
   - Device telemetry is accepted only for the enrolled device/bin.
   - Duplicate telemetry messages do not create duplicate records.
   - Dispatch cannot over-assign vehicle capacity or double-assign active work.
   - Completion, verification, exception handling, and vehicle release preserve history.
7. Complete browser, accessibility, and security checks.
8. Promote the same immutable artifact to production with a documented approval.
9. Verify dashboards and alerts, inspect error rates, and record the release commit, image digest, migration version, deployment time, and rollback decision.
10. Keep the prior known-good artifact and follow the rollback plan below.

## Rollback

- Stop promotion and route traffic to the previous known-good image if health checks or critical workflows fail.
- Prefer application rollback only when the current schema remains backward-compatible.
- Do not blindly reverse a destructive migration. Restore a tested backup into an isolated environment and follow the approved recovery plan.
- Record the incident, affected data window, recovery actions, and follow-up issue.
- Re-run smoke tests and confirm no duplicate dispatches or lost collection history before restoring normal traffic.

## Backup and recovery drill

At minimum, establish an owner, encrypted backup schedule, retention window, separate failure domain, access policy, and alert for missed backups.

For each drill:

1. Record the source backup timestamp and checksum/identifier.
2. Restore to a separate, isolated database.
3. Apply only the documented recovery steps.
4. Verify row counts and relationships for bins, telemetry, jobs, service events, vehicles, drivers, devices, and route plans.
5. Run migrations/status checks and application smoke tests against the restored database.
6. Measure recovery point objective (RPO) and recovery time objective (RTO).
7. Capture logs and results; fix any failures and repeat the drill.

A backup job reporting success is not proof that a restore works.

## Monitoring and incident response

Monitor and alert on:

- API 5xx rate, latency percentiles, readiness failures, and process restarts
- Database connectivity, connection-pool exhaustion, storage capacity, and backup age
- Telemetry ingestion rate, rejected/stale readings, duplicate/conflicting messages, and device last-seen age
- Approved jobs not dispatched, jobs stuck in assigned/in-progress, repeated exceptions, and unavailable vehicles
- Routing-provider timeouts/errors and optimizer failures
- Forecast unavailability, model version, input freshness, and prediction error once ground truth is available

Each alert needs a named owner, severity, response expectation, runbook, and escalation path. Do not log bearer tokens, device tokens, driver tokens, or full secret-bearing request headers.

## Evidence required to close this runbook

- [ ] Staging and production deployment records with immutable image digests
- [ ] HTTPS, secure-header, network-isolation, and secret-handling review
- [ ] Successful restore drill with measured RPO/RTO
- [ ] Monitoring dashboard and alert-delivery evidence
- [ ] Load test report with target volumes and measured results
- [ ] Security review and resolution of critical/high findings
- [ ] Post-deployment acceptance report signed by the project owner
