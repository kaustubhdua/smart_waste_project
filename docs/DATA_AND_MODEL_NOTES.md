# Data and model notes

This repository demonstrates a waste-collection pipeline. Treat generated or sample records as illustrative unless their provenance is explicitly documented.

## Pipeline boundaries
1. Preprocessing creates model-ready features from the input time series.
2. The prediction module estimates future fill level.
3. The priority module applies a three-input zero-order Sugeno fuzzy inference system to fill percentage, hours since verified emptying, and bin criticality.
4. The optimizer proposes routes subject to its configured constraints.
5. The Streamlit app presents the resulting data and route.

## Fuzzy priority model

The priority engine uses trapezoidal membership functions for low/medium/high fill, recent/aging/overdue service age, and low/medium/high criticality. It evaluates all 27 rule combinations with product firing strength and computes a bounded crisp score using the weighted-average defuzzification used by zero-order Sugeno systems.

The consequent anchors and input membership breakpoints are documented in `backend/app/priority.py`. They are engineering defaults for the demonstration, not universal municipal thresholds. Calibrate them with operators and field outcomes before using the score for real dispatch decisions. A missing verified-emptying timestamp is represented as zero elapsed hours rather than inventing service history.

## Forecast feature contract (schema version 2)

The one-step model is trained only on next-observation intervals of 30–90 minutes. The 1-hour lag is populated only when the previous observation is 30–90 minutes old. The 3-hour lag requires three consecutive 30–90 minute intervals and a total span of 150–210 minutes. The rolling mean uses a time-based six-hour window, excludes the current observation, and requires at least three prior readings. Training rows with incomplete or cadence-mismatched features are excluded rather than backfilled.

At inference, the API requires at least four readings in the most recent six hours, validates the last three intervals and the three-hour span, and uses the same feature definitions. Model artifacts carry a feature-schema version; legacy artifacts with the old observation-count semantics are skipped with `model_feature_schema_mismatch` and must be retrained. Predictions remain estimates of the next observation, not fixed-horizon forecasts.

## Interpretation
- A prediction is an estimate, not a sensor reading.
- A fuzzy priority score is a decision-support model encoded as fuzzy membership and rule inference; it is not a universal urgency label.
- A route is only as reliable as its coordinates, distance assumptions, vehicle capacities, and input validation.
- Synthetic or stale data must not be presented as live IoT telemetry.

## Validation when changing the pipeline
- Check missing values, duplicate bin/timestamp pairs, timestamp cadence, and out-of-range telemetry before model use.
- Keep preprocessing and inference feature order consistent.
- Test empty inputs and cases where no feasible route exists.
- Verify every assigned stop is present in the input and vehicle capacity constraints are respected.
- Record the dataset source, generation method, and time window when publishing results.

Run the automated tests and CI workflow before merging. Do not commit credentials or private operational data.
