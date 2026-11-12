# PBL implementation and deployment alignment

Review date: 12 November 2026  
Repository reviewed: `kaustubhdua/smart_waste_project`  
Reviewed source revision: `6dd26f09e00bab7a193df20a7fa840bdcdce8d6d`

## Supported application

The supported root application is the standalone Streamlit workspace in `app.py`. It provides six modules:

- Operations overview
- Collection point network
- Route planner
- Collection jobs
- Fleet
- Analytics

The workspace initializes generated example records (30 collection points, four vehicles, four example jobs and a 24-hour activity series). Users can edit records, create jobs, register points and vehicles, generate route plans, export CSV files, and save/restore a JSON workspace.

The workspace is session-scoped. It is not connected to physical bin sensors, municipal fleet infrastructure, a shared server database, or authenticated operator/driver accounts.

## Algorithms and interpretation

The active dashboard calculates priority with a weighted heuristic:

`P = min(100, 0.68 × fill_pct + 0.35 × min(hours_since_collection, 48) + criticality`

where criticality contributes 18 for High, 10 for Medium and 4 for Low.

The route planner calls `person4_optimization.py` and Google OR-Tools to solve a capacitated vehicle-routing problem. The solver's cost matrix is based on scaled Euclidean differences in latitude/longitude. The interface separately calculates approximate route kilometres with the Haversine formula and draws straight stop-to-stop lines on a Folium map. These are not road-network distances, turn-by-turn paths or dispatch ETAs.

The repository also contains separate preprocessing, Random Forest and Sugeno fuzzy-priority modules. They are not currently invoked by the active Streamlit application and should not be described as live dashboard functionality.

## Deployment verification finding

The Streamlit URL previously listed in the project report was checked on 12 November 2026 and returned an HTTP 200 page response. However, the page content appeared to be an older dashboard: it displayed collection controls, a synthetic/imported CSV notice, a missing-model-artifact message, a demo route-planning section and a reference to a backend route API. This does not match the supported standalone `app.py` application and current README.

The deployment source, repository, branch and entry-point should be checked in Streamlit Community Cloud. The public deployment should not be described as the current repository build until the exact intended commit is deployed and verified.

## CI and test coverage configured in the repository

The root Python CI workflow is configured to:

1. Install dependencies using Python 3.11.
2. Compile Python sources.
3. Run `python -m unittest discover -s tests -v`.
4. Start Streamlit and check its health endpoint.
5. Execute the page using Streamlit AppTest.

Existing unit tests cover preprocessing validation and historical feature handling, ML artifact training/loading/prediction, and CVRP input/capacity validation. This document records configured checks; it does not assert that a fresh run for a later commit passed.

## Release checklist

- [ ] Confirm the Streamlit app is connected to the intended repository and branch.
- [ ] Set the deployed entry point to root `app.py`.
- [ ] Deploy the exact reviewed commit.
- [ ] Confirm the public page matches the six-module WasteOps workspace.
- [ ] Run the repository CI workflow and retain the exact commit/run URLs.
- [ ] Test route planning with a known small case and verify every assigned vehicle stays within capacity.
- [ ] Test collection-job completion, fleet availability, CSV export and JSON restore.
- [ ] Keep report claims limited to the implemented prototype until field telemetry and a controlled pilot exist.

## Sources

- Repository README and root `app.py`.
- `person4_optimization.py` and `backend/app/priority.py`.
- `.github/workflows/ci.yml` and tests under `tests/`.
- [OR-Tools Vehicle Routing](https://developers.google.com/optimization/routing).
- [Streamlit Session State](https://docs.streamlit.io/develop/concepts/architecture/session-state).
- [OpenStreetMap Tile Usage Policy](https://operations.osmfoundation.org/policies/tiles/).
