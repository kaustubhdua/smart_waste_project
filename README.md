<div align="center">

# ♻️ WasteOps — Smart Waste Collection & Fleet Optimization

**Monitor → prioritize → plan → collect → improve**

A polished, interactive waste-collection operations workspace built with Streamlit, Python, Folium and Google OR-Tools.

[![Python CI](https://github.com/kaustubhdua/smart_waste_project/actions/workflows/ci.yml/badge.svg)](https://github.com/kaustubhdua/smart_waste_project/actions)
[![CodeQL](https://github.com/kaustubhdua/smart_waste_project/actions/workflows/codeql.yml/badge.svg)](https://github.com/kaustubhdua/smart_waste_project/actions/workflows/codeql.yml)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
![Routing](https://img.shields.io/badge/Optimization-OR--Tools-4285F4)

</div>

WasteOps provides an end-to-end interactive product experience without requiring a separate API server, database, cloud credentials, IoT hardware or paid routing service. The workspace opens with a ready-to-use service-area scenario. Collection points, jobs, vehicles and route plans are interactive and editable. Changes remain in the active browser session; use **Save workspace** to export a JSON snapshot and **Restore workspace** to continue from a saved snapshot. This standalone edition does not connect to municipal infrastructure or physical sensors.

## Product modules

- **Operations overview:** fleet and collection KPIs, service-area map, priority queue, activity timeline and recent events.
- **Collection point network:** searchable bins, area/type/status filters, map and table views, fill/battery controls and registration.
- **Route planner:** configurable pickup threshold, fleet selection, capacity-aware OR-Tools CVRP optimization, route map, vehicle schedules and job creation.
- **Collection management:** create and filter jobs, assign/update statuses, complete service and automatically reset collection-point fill.
- **Fleet management:** vehicle and driver roster, capacity/fuel indicators, availability controls and vehicle registration.
- **Performance analytics:** fill distribution, service mix, activity trends and CSV exports.
- **Workspace continuity:** export and restore the complete workspace as JSON, or reset it from the sidebar.

## Run locally

Requirements: Python 3.11 or newer.

```bash
git clone https://github.com/kaustubhdua/smart_waste_project.git
cd smart_waste_project
python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
streamlit run app.py
```

Open the local URL printed by Streamlit (normally http://localhost:8501).

## Deploy

The app can be deployed directly to Streamlit Community Cloud:

1. Sign in at https://share.streamlit.io/.
2. Select this GitHub repository and the `main` branch.
3. Set the app entry point to `app.py`.
4. Deploy.

No environment secrets or backend services are required. The map uses public OpenStreetMap tiles and the Python dependencies are declared in `requirements.txt`.

## Route planning

The route planner calls the repository's OR-Tools capacitated vehicle-routing solver. It distributes collection stops across available vehicles subject to vehicle capacity. The displayed route distance is an estimate derived from geographic coordinates; the map connects the planned stops and does not claim turn-by-turn road routing.

## Project structure

| Path | Purpose |
|---|---|
| `app.py` | Complete Streamlit product and interactive workspace |
| `person4_optimization.py` | OR-Tools vehicle-routing solver |
| `person1_preprocessing.py` | Data preparation utilities |
| `person2_ml_prediction.py` | Optional model-training utilities; not required by the app |
| `person3_fuzzy_logic.py` | Priority-scoring utilities |
| `tests/` | Python unit tests |
| `.streamlit/config.toml` | Theme configuration |
| `requirements.txt` | Runtime dependencies |

## Tests

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m compileall -q app.py person1_preprocessing.py person2_ml_prediction.py person3_fuzzy_logic.py person4_optimization.py
```

Route distance is estimated from geographic coordinates; it is not a road-network distance or a field-validated dispatch ETA. Workspace values are editable planning inputs, not a live sensor feed.
