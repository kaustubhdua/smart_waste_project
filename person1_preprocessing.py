import numpy as np
import pandas as pd


def generate_synthetic_bin_data(num_bins=20, days=30, seed=42):
    """Generate synthetic IoT waste-bin observations for demonstration."""
    np.random.seed(seed)
    date_range = pd.date_range(end=pd.Timestamp.now(), periods=days * 24, freq="h")

    data = []
    base_lat, base_lon = 28.5355, 77.3910

    for bin_id in range(1, num_bins + 1):
        lat = base_lat + np.random.uniform(-0.05, 0.05)
        lon = base_lon + np.random.uniform(-0.05, 0.05)
        capacity_liters = np.random.choice([100, 200, 500])
        criticality = np.random.choice(["High", "Medium", "Low"], p=[0.2, 0.5, 0.3])
        current_fill = np.random.uniform(5, 20)

        for timestamp in date_range:
            hour = timestamp.hour
            hourly_rate = (
                np.random.uniform(3, 8)
                if 8 <= hour <= 20
                else np.random.uniform(0.5, 2)
            )
            current_fill += hourly_rate

            if current_fill >= 90 or (
                current_fill > 70 and np.random.rand() < 0.15
            ):
                current_fill = np.random.uniform(0, 5)

            data.append(
                {
                    "timestamp": timestamp,
                    "bin_id": f"BIN_{bin_id:03d}",
                    "latitude": lat,
                    "longitude": lon,
                    "capacity_liters": capacity_liters,
                    "criticality": criticality,
                    "fill_level_pct": round(min(current_fill, 100.0), 2),
                    "temperature_c": round(np.random.uniform(20, 38), 1),
                }
            )

    return pd.DataFrame(data)


def preprocess_data(df):
    """Clean sensor data and build features using only information available before prediction time."""
    required = {
        "timestamp",
        "bin_id",
        "latitude",
        "longitude",
        "capacity_liters",
        "criticality",
        "fill_level_pct",
        "temperature_c",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    if df["timestamp"].isna().any():
        raise ValueError("timestamp contains invalid values")

    df = df.sort_values(by=["bin_id", "timestamp"]).reset_index(drop=True)
    df["fill_level_pct"] = pd.to_numeric(df["fill_level_pct"], errors="coerce").clip(0, 100)
    if df["fill_level_pct"].isna().any():
        raise ValueError("fill_level_pct contains invalid values")

    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

    grouped_fill = df.groupby("bin_id")["fill_level_pct"]
    df["fill_lag_1h"] = grouped_fill.shift(1)
    df["fill_lag_3h"] = grouped_fill.shift(3)
    # Shift the rolling window so the current target is never included.
    df["rolling_mean_6h"] = grouped_fill.transform(
        lambda x: x.shift(1).rolling(6, min_periods=1).mean()
    )

    # Leave insufficient-history rows missing. Backfilling from later rows
    # would leak future fill values into features for earlier prediction times.
    # The model-training path drops rows without complete historical features.
    return df
