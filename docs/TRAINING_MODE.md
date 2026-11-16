# WasteOps training workspace

This guide starts a fully interactive local training environment. It uses the same API, database, authentication, routing, prioritization and driver workflows as the API-backed product, with generated scenario records preloaded for safe practice.

## 1. Configure the environment

```bash
cp .env.example .env
```

Set unique local values in `.env`:

- `POSTGRES_PASSWORD`: a long random password for the local database.
- `API_TOKEN`: a separate random bootstrap secret of at least 32 characters.
- `SEED_DEMO_DATA=true`: opt in to the generated training scenario.
- Keep `APP_ENV=development` for this local training stack.

Never use the example credentials in a public deployment. Demo seeding is rejected when `APP_ENV=production`.

## 2. Start the platform

```bash
docker compose up --build -d
docker compose ps
```

Wait until the database, API and web containers report healthy.

- Operator console: http://localhost:8080
- Driver workspace: http://localhost:8080/driver.html
- API liveness: http://localhost:8000/health
- API readiness: http://localhost:8000/health/ready

The API container applies Alembic migrations before it seeds the training records and starts the server.

## 3. Create the administrator

The operator console is the sign-in interface; create the initial administrator once through the API bootstrap endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/auth/bootstrap \
  -H 'Content-Type: application/json' \
  -H 'X-Bootstrap-Token: YOUR_API_TOKEN' \
  -d '{"username":"admin","password":"Use-a-unique-password-12+"}'
```

Use the `API_TOKEN` value from your local `.env` as the bootstrap header and a unique password of at least 12 characters. After bootstrap, sign in using the named administrator account.

The shared bootstrap token is not the normal operator login credential. Use named accounts and expiring browser sessions for day-to-day access.

## 4. Sign in to a training driver

The seed creates four driver identities. When a driver is first created, its random one-time token is printed in the API container logs:

```bash
docker compose logs api
```

Find the line beginning `ONE-TIME TRAINING DRIVER CREDENTIAL`. Enter the corresponding driver ID and token in the Driver workspace. The token is stored as a hash in the database and is not displayed again. If the token is lost, an administrator can rotate that driver's credential through the operator console.

Two collection jobs are pre-assigned to training vehicles so the driver workflow can be exercised immediately. Other detected jobs can be approved and dispatched by an operator.

## 5. Suggested end-to-end exercise

1. Inspect the service-area map, bin history and priority queue.
2. Open a detected collection job and approve it.
3. Optimize and dispatch approved work to available vehicles.
4. Sign in as the matching driver and load assigned stops.
5. Start a stop, mark it collected, or report an exception.
6. Return to the operator console and verify completed work.
7. Review service events and audit history.
8. Repeat with another vehicle and compare route capacity and distance.

The driver application caches the last-synced stops and queues idempotent actions while offline. Pending actions sync when the driver page is open or reopened with connectivity; this is not a background-sync guarantee.

## 6. Reset the training database

The seed is idempotent and does not overwrite existing operator edits. To start over, stop the stack and remove its local database volume:

```bash
docker compose down -v
docker compose up --build -d
```

**Warning:** `docker compose down -v` permanently deletes all data in this local Compose database volume, including operator accounts and changes.

## Data interpretation

The preloaded records are generated training examples. They exercise the real application code and persist like ordinary records, but they are not live sensor readings, actual vehicle GPS traces or verified municipal collection events. The compact **Training workspace** indicator is the user-facing environment disclosure; individual rows are kept uncluttered. Do not use this environment as evidence of field performance or real-world savings.

For production requirements and release gates, see `docs/DEPLOYMENT_RUNBOOK.md` and `docs/IMPLEMENTATION_STATUS.md`.
