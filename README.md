# Smart Waste Collection & Route Optimisation

<p align="center"><strong>Prediction → priority → routing</strong><br/>An end-to-end decision pipeline connecting machine-learning forecasts to vehicle-routing decisions.</p>

> **Status:** engineering prototype using synthetic IoT-style data. This demonstrates the decision pipeline; it is not evidence of a live municipal deployment.

## Engineering snapshot

**Problem:** collection decisions need to connect predicted bin state with operational urgency and vehicle constraints.

**Pipeline:** IoT-style time series → feature engineering → Random Forest prediction → continuous priority scoring → Google OR-Tools routing → Streamlit/Folium decision surface.

**Technical proof:** time-series features · Random Forest regression · 0–100 priority scoring · CVRP optimisation · geospatial dashboard.

## Evaluation contract

Run the app's model evaluation in an environment with the dependencies from `requirements.txt` installed:

~~~bash
python person2_ml_prediction.py
~~~

The training script now reports a chronological holdout comparison against a mean-only baseline (MAE and RMSE). These values are for generated/synthetic data and one temporal split only; they are not field accuracy, operational savings, or evidence that a deployed collection service improved. Record the dataset-generation seed and exact run when publishing results. For a stronger evaluation, reserve later dates and unseen bins, repeat across multiple seeds, and compare against a last-observation baseline before interpreting model performance.

## Why the pipeline matters

The project deliberately connects stages that are often presented as separate demos: model output becomes a prioritisation signal, prioritisation becomes an optimisation input, and the resulting route is exposed for inspection.

## Boundaries

The data is synthetic and the routing environment is simulated. Model accuracy, route quality and operational savings should therefore be evaluated as engineering experiments rather than real-world impact.

---

# 🗑️ Smart Waste Collection & Route Optimization System<img width="1897" height="866" alt="Screenshot 2026-07-22 040317" src="https://github.com/user-attachments/assets/44c32438-619c-4c95-aef4-2af907966abf" />


An end-to-end, AI-powered waste management pipeline designed to monitor IoT-enabled bins, predict fill levels, score collection priorities using continuous logic, and optimise collection truck routes using Google OR-Tools.

---

## 🌟 Key Features

* **Data Preprocessing & Feature Engineering**: Generates and processes IoT time-series data, engineering key lag features and rolling averages.
* **ML Fill Level Prediction**: Predicts future bin capacity levels using a Random Forest Regressor model.
* **Dynamic Priority Scoring**: Calculates a normalised 0–100 priority score using mathematical membership curves taking fill %, time elapsed, and bin criticality into account.
* **Route Optimisation (CVRP)**: Solves the Capacitated Vehicle Routing Problem using Google OR-Tools to minimise travel distances while honouring truck capacity limits.
* **Interactive Dashboard**: Features a live Streamlit interface with Folium map rendering, dynamic priority thresholds, and route visualisation.

---

## 🛠️ Project Architecture & Modules

```text
smart_waste_project/
│
├── person1_preprocessing.py   # IoT synthetic data generator & feature engineering
├── person2_ml_prediction.py   # Random Forest model training & persistence
├── person3_fuzzy_logic.py     # Priority engine (Fuzzy logic logic/membership math)
├── person4_optimization.py    # Google OR-Tools Vehicle Routing Problem (VRP) solver
├── app.py                     # Streamlit frontend & geospatial Folium map dashboard
├── cleaned_waste_data.csv     # Preprocessed dataset
├── waste_model.pkl            # Trained ML model artefact
└── requirements.txt           # Project dependencies
