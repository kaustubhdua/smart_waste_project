# Security threat model

## Scope and honest status

This document identifies security boundaries for the Smart Waste Collection Platform. It is not a penetration-test report or certification. The current operator API uses one shared bearer token; that is a prototype boundary and must not be represented as multi-user authentication or role-based access control.

## Assets

- Operator credential and database credentials
- Device and driver credentials
- Bin locations, telemetry, collection schedules, routes, and service history
- Vehicle capacity/availability and dispatch decisions
- Model artifacts and any imported datasets
- Database backups, logs, and deployment configuration

## Trust boundaries

1. Browser to reverse proxy/web server
2. Reverse proxy to API
3. API to database
4. Device to telemetry endpoint
5. Driver client to driver endpoints
6. API to external routing service
7. CI workflow to build artifacts and deployment credentials
8. Backup storage to recovery environment

## Threats and required controls

| Threat | Impact | Required controls / verification |
|---|---|---|
| Shared operator token is leaked | Any holder may perform operator actions | Replace with managed identity and per-user RBAC; short-lived sessions/tokens, revocation, rate limits, MFA where supported; test each role against every protected route |
| Device token theft or replay | False readings or data tampering for a bin | TLS, per-device scope, rotation/revocation, idempotency, anomaly detection, rate limits, clock validation; test revoked and cross-bin credentials |
| Driver credential misuse | Unauthorized job transitions or operational disruption | Short-lived driver identity, vehicle-scoped authorization, revocation, audit events; test cross-driver and cross-vehicle access |
| Public API/database exposure | Data theft or service compromise | Private network, TLS ingress, no public DB port, firewall/security groups, secure headers, deployment scan |
| Secret leakage in Git/logs/browser | Account compromise | Secret manager, scanning, log redaction, token-free client bundles, rotate exposed credentials and inspect history |
| Malicious/oversized CSV | Resource exhaustion or polluted data | Upload limits, schema validation, row limits, transaction safety, content validation, rate limits and abuse tests |
| Duplicate/concurrent dispatch | Double assignment or capacity violations | Database constraints/transactions, concurrency tests, idempotent operations and invariants checked after racing requests |
| Routing-provider outage or manipulated response | Dispatch failure or unsafe route plan | Contracted/self-hosted provider, timeouts, bounded input, explicit failure behavior, response validation and manual fallback |
| Malicious model artifact or poisoned data | Code execution or incorrect forecasts | Treat serialized model artifacts as trusted code; restrict artifact writers, checksum/version artifacts, validate training provenance, evaluate model quality, keep model-assisted dispatch disabled until approved |
| Backup theft or failed recovery | Sensitive location data exposure or prolonged outage | Encryption, least privilege, isolated retention, restore drills, access logs and measured RPO/RTO |
| Vulnerable dependencies or CI supply chain | Remote compromise or malicious build | Pinned dependencies, automated dependency/security updates, CodeQL, least-privilege CI permissions, reviewed workflow changes and immutable release artifacts |
| Privacy/retention failure | Excess collection of location/operational data | Define purpose, retention, access policy, deletion/export process and applicable local legal review before live deployment |

## Minimum security test matrix

- [ ] Missing, malformed, incorrect, expired, and revoked credentials are rejected.
- [ ] Every role is tested against read/write/delete/dispatch/verification/export endpoints.
- [ ] Device A cannot submit telemetry for Bin B.
- [ ] Driver A cannot read or transition Driver B's vehicle jobs.
- [ ] Cross-origin requests are limited to explicitly trusted HTTPS origins.
- [ ] Oversized CSV, malformed values, timestamp skew, duplicate IDs, and invalid transitions fail safely.
- [ ] Parallel dispatch attempts cannot assign a job or vehicle inconsistently.
- [ ] Secrets are absent from browser bundles, logs, screenshots, workflow output, and tracked configuration.
- [ ] Dependency and static-analysis findings are reviewed, not merely run.
- [ ] Restore permissions and backup access are tested independently of application credentials.

## Release decision

Do not expose the system to public or municipal operations until the shared operator credential limitation is resolved, the deployment boundary is reviewed, and all P0 gates in [the release checklist](RELEASE_CHECKLIST.md) have evidence. Hardware readiness, model quality, and operational savings require real-world evidence and cannot be proven by source code or CI alone.
