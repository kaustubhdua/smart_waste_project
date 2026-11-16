<div align="center">

# ♻️ WasteOps — Smart Waste Collection & Fleet Optimization

**Monitor → prioritize → dispatch → collect → verify**

A browser-based waste operations platform with persistent records, authenticated operator and driver workflows, telemetry ingestion, fuzzy prioritization and capacity-aware route optimization.

</div>

## Product experience

The primary application is the API-backed platform:

- **Operator console:** collection-point map, telemetry history, priority queue, job approval, fleet management, route planning, dispatch, audit and exports.
- **Driver workspace:** vehicle-scoped stops, navigation handoff, start/complete/exception actions and an offline action queue.
- **Operations backend:** FastAPI, PostgreSQL, Alembic migrations, device-scoped ingestion, idempotency, role-aware authentication and service-event history.
- **Optimization:** Sugeno fuzzy urgency scoring, road-network distance/geometry provider and Google OR-Tools capacity-constrained vehicle routing.
- **Forecasting:** optional versioned Random Forest next-observation inference; disabled for dispatch by default.

The repository also retains a lightweight standalone Streamlit planning workspace in `app.py`. It is session-scoped and does not share state with the API-backed product.

## Run a populated training workspace

Requirements: Docker Compose v2.

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` and `API_TOKEN` with unique local secrets.
3. Set `SEED_DEMO_DATA=true` for a non-production training environment.
4. Start the complete stack:

```bash
docker compose up --build -d
```

5. Open:
   - Operator console: http://localhost:8080
   - Driver workspace: http://localhost:8080/driver.html
   - API health: http://localhost:8000/health

The training seed is idempotent and preloads 16 collection points, four vehicles, six hourly observations per point, driver identities and collection jobs in multiple workflow states. Newly created driver tokens are printed once in the API container logs:

```bash
docker compose logs api
```

Use the one-time administrator bootstrap flow in the operator console, then sign in and exercise approval, dispatch, driver actions, completion and verification. The console shows a compact **Training workspace** indicator; it does not repeat demo-source labels on every operational row. This environment indicator is deliberate because generated training records must not be mistaken for readings from physical devices.

For an empty environment, set `SEED_DEMO_DATA=false` and start with a fresh database. Removing the local database volume is destructive:

```bash
docker compose down -v
```

See [the training guide](docs/TRAINING_MODE.md) for the complete walkthrough.

## Run the standalone Streamlit workspace

Requirements: Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

This lightweight edition provides editable bins, jobs, vehicles, OR-Tools planning, analytics and JSON/CSV export. Its state is browser-session scoped and its coordinate-based route display is not turn-by-turn road routing.

## Repository layout

| Path | Purpose |
|---|---|
| `backend/app/` | FastAPI application, persistence, auth, routing, optimization and priority |
| `backend/migrations/` | Alembic database migrations |
| `backend/scripts/seed_demo.py` | Opt-in, idempotent training scenario |
| `backend/tests/` | API, auth, configuration, routing and optimizer tests |
| `web/` | Operator console, driver workspace and offline service worker |
| `app.py` | Standalone Streamlit planning workspace |
| `person1_preprocessing.py` | Dataset preprocessing |
| `person2_ml_prediction.py` | Model training and artifact generation |
| `person3_fuzzy_logic.py` | Fuzzy-priority compatibility API |
| `person4_optimization.py` | Standalone OR-Tools CVRP module |
| `docs/` | Implementation status, training, security and deployment runbooks |

## Verification

The repository's GitHub Actions workflows cover Python tests, API/auth/routing tests, browser checks, accessibility checks, container builds and Compose smoke tests. A configured workflow is not proof of a passing run: inspect the exact commit's Actions result before release.

## Data and production boundaries

The training environment executes the real application code and persists its workflow changes, but its preloaded records are generated examples. They are not live municipal telemetry or independently verified collection events. The Random Forest component predicts the next observed fill value; it is not a validated long-horizon forecast. Public OSRM is a development routing dependency without a service guarantee.

Production still requires calibrated hardware, representative field validation, a contracted or self-hosted routing service, HTTPS ingress, managed secrets, durable backups, monitoring, load/security/accessibility review and a controlled municipal pilot. See [implementation status](docs/IMPLEMENTATION_STATUS.md), [deployment runbook](docs/DEPLOYMENT_RUNBOOK.md) and [release checklist](docs/RELEASE_CHECKLIST.md).
