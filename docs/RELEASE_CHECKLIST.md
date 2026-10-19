# Release acceptance checklist

Use this checklist for each release. Mark a task complete only when evidence is linked from a CI run, test report, deployment record, restore drill or pilot report. An unchecked item is not implied to be complete because a related feature exists.

## P0 — required before production exposure

- [ ] Replace shared operator bearer-token authentication with managed per-user identity and tested role-based authorization.
- [ ] Verify authorization on every protected endpoint, including read, create, update, delete, export and operational actions.
- [ ] Add rate limiting, session/token expiry, revocation, secret rotation and security audit events.
- [ ] Deploy behind HTTPS/TLS with a production domain, private database networking, secure headers and explicit CORS origins.
- [ ] Store secrets in a managed secret store; verify no credentials are present in repository history, build logs or client bundles.
- [ ] Configure automated encrypted backups, retention, access controls, and complete a restore drill with recorded RPO/RTO.
- [ ] Configure logs, metrics, uptime checks, alert routing, incident ownership and runbooks.
- [ ] Replace public demo OSRM with a contracted or self-hosted provider and verify outage handling.
- [ ] For an IoT deployment, calibrate physical sensors and record a supervised field-validation report. For a simulation-only release, clearly scope the product as a simulation and do not claim hardware readiness.

## P1 — complete release quality

- [ ] Browser-driven end-to-end tests cover operator and driver journeys, including authentication, errors and responsive layouts.
- [ ] Lifecycle tests cover create/approve/dispatch/start/complete/verify, vehicle release, exceptions, duplicate requests, retries and concurrent dispatch.
- [ ] Migration tests cover an empty database and supported upgrade paths using the production database engine.
- [ ] Load/soak tests exercise documented target volumes and concurrency; publish results and limits.
- [ ] Accessibility review covers keyboard use, focus, contrast, labels, error announcements and mobile usability.
- [ ] ML evaluation uses a chronological holdout, compares simple baselines, reports MAE/RMSE by horizon and cohort, and records data leakage checks.
- [ ] Model predictions have a documented horizon, quality threshold, fallback and versioned artifact; model-assisted dispatch remains disabled until field evidence supports it.
- [ ] Pilot evaluation compares planned vs actual route time, collection completion, sensor error, exceptions and operator feedback against a baseline.
- [ ] Rollback, release tagging, staging promotion and post-release review are documented and rehearsed.

## P2 — maturity and portfolio presentation

- [ ] Add spatial indexes/geospatial column usage if spatial query needs and benchmarks justify it.
- [ ] Add retention policies, exportable audit reports and operational analytics.
- [ ] Publish architecture and data-flow diagrams, screenshots or a recorded demo, API examples and a limitations section.
- [ ] Keep dependency updates, security checks and CI status visible in the README.
- [ ] Review issues, pull requests and release notes before tagging a stable release.

## Evidence record

For each release, record:
- Commit SHA and release tag:
- CI run URLs:
- Environment and deployment date:
- Security review and findings:
- Backup restore drill URL, RPO and RTO:
- Load-test report and target volumes:
- Sensor/ML/pilot report or explicit simulation-only scope:
- Known limitations and accepted risks:
- Release decision, approver and rollback owner:

## Portfolio-complete vs production-ready

A reproducible portfolio demo may be considered complete when its advertised flows and automated tests work, documentation is accurate, demo data is clearly labelled, and limitations are visible. It must not be described as production-ready until the P0 and applicable P1 gates above have evidence.
