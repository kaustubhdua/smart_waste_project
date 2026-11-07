import joblib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

FEATURES = [
    "capacity_liters", "temperature_c", "hour", "day_of_week",
    "is_weekend", "fill_lag_1h", "fill_lag_3h", "rolling_mean_6h",
]
TARGET = "next_fill_level_pct"
MODEL_FILENAME = "models/waste_model.pkl"
FEATURE_SCHEMA_VERSION = 2
MIN_TARGET_INTERVAL_MINUTES = 30
MAX_TARGET_INTERVAL_MINUTES = 90


def train_ml_model(csv_path="cleaned_waste_data.csv", model_path=MODEL_FILENAME):
    """Train and evaluate a one-observation-ahead model on hourly-like telemetry."""
    df = pd.read_csv(csv_path)
    if "timestamp" not in df.columns or "bin_id" not in df.columns or "fill_level_pct" not in df.columns:
        raise ValueError("Dataset must contain timestamp, bin_id and fill_level_pct")
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    if df["timestamp"].isna().any():
        raise ValueError("Dataset contains invalid timestamps")
    if df["bin_id"].isna().any():
        raise ValueError("Dataset contains missing bin_id values")
    if df.duplicated(["bin_id", "timestamp"]).any():
        raise ValueError("Dataset contains duplicate timestamps for the same bin")
    missing = set(FEATURES).difference(df.columns)
    if missing:
        raise ValueError(f"Dataset is missing features: {sorted(missing)}")
    for feature in FEATURES:
        df[feature] = pd.to_numeric(df[feature], errors="coerce")
        if np.isinf(df[feature].to_numpy(dtype=float)).any():
            raise ValueError(f"{feature} contains infinite values")
    df["fill_level_pct"] = pd.to_numeric(df["fill_level_pct"], errors="coerce")
    if not np.isfinite(df["fill_level_pct"].to_numpy(dtype=float)).all():
        raise ValueError("fill_level_pct contains missing or non-finite values")
    if not df["fill_level_pct"].between(0, 100).all():
        raise ValueError("fill_level_pct must be between 0 and 100")

    df = df.sort_values(["bin_id", "timestamp"]).reset_index(drop=True)
    grouped = df.groupby("bin_id", sort=False)
    df["_target_timestamp"] = grouped["timestamp"].shift(-1)
    df[TARGET] = grouped["fill_level_pct"].shift(-1)
    df["_target_interval_minutes"] = (
        df["_target_timestamp"] - df["timestamp"]
    ).dt.total_seconds().div(60)

    model_df = df.dropna(subset=FEATURES + [TARGET, "_target_timestamp"]).copy()
    model_df = model_df[
        model_df["_target_interval_minutes"].between(
            MIN_TARGET_INTERVAL_MINUTES, MAX_TARGET_INTERVAL_MINUTES
        )
    ].copy()
    if len(model_df) < 20:
        raise ValueError(
            "Not enough valid rows with complete history and a 30–90 minute next observation"
        )

    cutoff = model_df["timestamp"].quantile(0.8)
    train_mask = (model_df["timestamp"] < cutoff) & (model_df["_target_timestamp"] < cutoff)
    test_mask = model_df["timestamp"] >= cutoff
    X_train, y_train = model_df.loc[train_mask, FEATURES], model_df.loc[train_mask, TARGET]
    X_test, y_test = model_df.loc[test_mask, FEATURES], model_df.loc[test_mask, TARGET]
    if X_train.empty or X_test.empty:
        raise ValueError("Unable to create chronological train/test split")

    baseline = DummyRegressor(strategy="mean").fit(X_train, y_train)
    baseline_predictions = baseline.predict(X_test)
    persistence_predictions = model_df.loc[test_mask, "fill_level_pct"].to_numpy()
    model = RandomForestRegressor(n_estimators=200, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    predictions = model.predict(X_test)
    metrics = {
        "train_rows": int(len(X_train)),
        "holdout_rows": int(len(X_test)),
        "split_cutoff_utc": cutoff.isoformat(),
        "target_interval_minutes": [MIN_TARGET_INTERVAL_MINUTES, MAX_TARGET_INTERVAL_MINUTES],
        "mean_baseline_mae": float(mean_absolute_error(y_test, baseline_predictions)),
        "persistence_baseline_mae": float(mean_absolute_error(y_test, persistence_predictions)),
        "random_forest_mae": float(mean_absolute_error(y_test, predictions)),
        "mean_baseline_rmse": float(mean_squared_error(y_test, baseline_predictions) ** 0.5),
        "persistence_baseline_rmse": float(mean_squared_error(y_test, persistence_predictions) ** 0.5),
        "random_forest_rmse": float(mean_squared_error(y_test, predictions) ** 0.5),
        "evaluation_note": "Chronological holdout only; synthetic data is not evidence of field performance.",
    }
    artifact = {
        "model": model,
        "features": FEATURES,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "target": TARGET,
        "trained_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "training_rows": int(len(model_df)),
        "metrics": metrics,
    }
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    print("Chronological holdout metrics (not field performance):")
    for key, value in metrics.items():
        print(f"  {key}: {value}")
    print(f"Saved model artifact to {model_path}")
    return model


def load_ml_model(model_path=MODEL_FILENAME):
    """Load a trained artifact; return None when no artifact exists."""
    import os
    if not os.path.exists(model_path):
        return None
    artifact = joblib.load(model_path)
    if not isinstance(artifact, dict) or "model" not in artifact:
        raise ValueError("Legacy model artifact has no feature-schema metadata; retrain it with person2_ml_prediction.py")
    if artifact.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        raise ValueError("Model artifact feature schema is incompatible; retrain it with person2_ml_prediction.py")
    return artifact["model"]


def predict_next_fill(model, rows):
    """Predict the next observed fill level from rows containing the declared features."""
    if model is None:
        return None
    missing = set(FEATURES).difference(rows.columns)
    if missing:
        raise ValueError(f"Prediction rows are missing features: {sorted(missing)}")
    frame = rows[FEATURES].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(frame.to_numpy(dtype=float)).all():
        raise ValueError("Prediction features contain missing or non-finite values")
    values = model.predict(frame)
    if not np.isfinite(np.asarray(values, dtype=float)).all():
        raise ValueError("Model returned non-finite predictions")
    return pd.Series(values, index=rows.index).clip(0, 100)


if __name__ == "__main__":
    train_ml_model()
