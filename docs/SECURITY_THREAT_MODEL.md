# Security threat model

## Scope and honest status

This document identifies security boundaries for the Smart Waste Collection Platform. It is not a penetration-test report or certification. The operator API now supports named admin/operator accounts, salted PBKDF2 password hashes, eight-hour opaque sessions stored as SHA-256 hashes, account lockout after repeated failures, account/session revocation, administrator-only user/device/driver credential management, and security audit events. This is an application-level identity foundation, not a third-party identity provider or penetration-test certification.

## Assets

- Operator credential and database credentials
- Device and driver credentials
- Bin locations, telemetry, collection schedules, routes, and service history
- Locally cached driver stop details and queued offline collection actions
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
| Bootstrap secret is leaked or initial admin compromised | Attacker may create the first administrator or gain privileged access | Keep API_TOKEN in a secret manager, use one-time bootstrap only, create named users, rotate bootstrap secret, enforce TLS, use the included Nginx per-client login/bootstrap rate limit with a correctly configured trusted-proxy IP chain, add MFA through an identity provider, and verify bootstrap cannot be repeated |
| Device token theft or replay | False readings or data tampering for a bin | TLS, per-device scope, rotation/revocation, idempotency, anomaly detection, rate limits, clock validation; test revoked and cross-bin credentials |
| Driver credential misuse | Unauthorized job transitions or operational disruption | Vehicle-scoped authorization, credential revocation, audit events, request-bound idempotency keys; test cross-driver, cross-vehicle and replay behavior |
| Shared or lost driver device | Cached stop/location data or queued actions may be exposed to another device user | Device lock, per-driver sessionStorage credentials, no driver token in IndexedDB, clear cached stops on sign-out, restrict browser-profile access and define device wipe/retention procedures |
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

- [x] Missing, malformed, incorrect, expired, and revoked operator sessions are rejected by automated tests.
- [x] Admin/operator privilege boundaries, account disablement, one-time bootstrap and last-admin protection are covered by automated tests.
- [ ] The included Nginx limit is per observed client IP and must be configured with the trusted proxy chain in production; MFA/SSO and a formal penetration test remain outstanding.
- [ ] Every role is tested against read/write/delete/dispatch/verification/export endpoints.
- [ ] Device A cannot submit telemetry for Bin B.
- [ ] Driver A cannot read or transition Driver B's vehicle jobs.
- [x] Replaying the same driver action key returns the original result without a second service event; reusing the key with a different payload is rejected.
- [ ] Cross-origin requests are limited to explicitly trusted HTTPS origins.
- [ ] Oversized CSV, malformed values, timestamp skew, duplicate IDs, and invalid transitions fail safely.
- [ ] Parallel dispatch attempts cannot assign a job or vehicle inconsistently.
- [ ] Secrets are absent from browser bundles, logs, screenshots, workflow output, and tracked configuration.
- [ ] Dependency and static-analysis findings are reviewed, not merely run.
- [ ] Restore permissions and backup access are tested independently of application credentials.

## Release decision

Do not expose the system to public or municipal operations until bootstrap secret handling, ingress rate limiting, MFA/SSO decision, deployment boundary review, and all P0 gates in [the release checklist](RELEASE_CHECKLIST.md) have evidence. Hardware readiness, model quality, and operational savings require real-world evidence and cannot be proven by source code or CI alone.
