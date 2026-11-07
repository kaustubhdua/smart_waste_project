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

## Interpretation
- A prediction is an estimate, not a sensor reading.
- A fuzzy priority score is a decision-support model encoded as fuzzy membership and rule inference; it is not a universal urgency label.
- A route is only as reliable as its coordinates, distance assumptions, vehicle capacities, and input validation.
- Synthetic or stale data must not be presented as live IoT telemetry.

## Validation when changing the pipeline
- Check missing values, duplicate identifiers, and out-of-range fill percentages before model use.
- Keep preprocessing and inference feature order consistent.
- Test empty inputs and cases where no feasible route exists.
- Verify every assigned stop is present in the input and vehicle capacity constraints are respected.
- Record the dataset source, generation method, and time window when publishing results.

Run the automated tests and CI workflow before merging. Do not commit credentials or private operational data.
