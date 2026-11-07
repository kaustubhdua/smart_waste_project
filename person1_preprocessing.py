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
    """Validate telemetry and build timestamp-aware, strictly historical features."""
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
    if df.empty:
        raise ValueError("Dataset contains no telemetry rows")
    df = df.copy()
    if df["bin_id"].isna().any() or df["bin_id"].astype(str).str.strip().eq("").any():
        raise ValueError("bin_id contains missing or empty values")
    df["bin_id"] = df["bin_id"].astype(str).str.strip()
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    if df["timestamp"].isna().any():
        raise ValueError("timestamp contains invalid values")

    numeric_ranges = {
        "latitude": (-90.0, 90.0),
        "longitude": (-180.0, 180.0),
        "capacity_liters": (0.0, None),
        "fill_level_pct": (0.0, 100.0),
        "temperature_c": (-50.0, 80.0),
    }
    for column, (minimum, maximum) in numeric_ranges.items():
        df[column] = pd.to_numeric(df[column], errors="coerce")
        values = df[column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError(f"{column} contains missing or non-finite values")
        if (values < minimum).any() or (maximum is not None and (values > maximum).any()):
            if column == "fill_level_pct":
                raise ValueError("fill_level_pct must be between 0 and 100; values are not silently clipped")
            raise ValueError(f"{column} contains values outside its valid range")

    if (df["capacity_liters"] <= 0).any():
        raise ValueError("capacity_liters must be greater than zero")
    if df.duplicated(["bin_id", "timestamp"]).any():
        raise ValueError("Dataset contains duplicate timestamps for the same bin")

    df = df.sort_values(["bin_id", "timestamp"]).reset_index(drop=True)
    df["hour"] = df["timestamp"].dt.hour
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

    grouped = df.groupby("bin_id", sort=False)
    grouped_fill = grouped["fill_level_pct"]
    interval_1 = grouped["timestamp"].diff().dt.total_seconds().div(60)
    interval_2 = interval_1.groupby(df["bin_id"], sort=False).shift(1)
    interval_3 = interval_1.groupby(df["bin_id"], sort=False).shift(2)
    elapsed_3 = grouped["timestamp"].diff(3).dt.total_seconds().div(60)

    valid_one_hour = interval_1.between(30, 90)
    valid_three_hour = (
        elapsed_3.between(150, 210)
        & valid_one_hour
        & interval_2.between(30, 90)
        & interval_3.between(30, 90)
    )
    df["fill_lag_1h"] = grouped_fill.shift(1).where(valid_one_hour)
    df["fill_lag_3h"] = grouped_fill.shift(3).where(valid_three_hour)

    # A true time-based rolling window excludes the current observation.
    # Requiring three prior readings prevents a one- or two-point "6h mean"
    # from masquerading as a six-hour history feature.
    df["rolling_mean_6h"] = np.nan
    for _, indices in df.groupby("bin_id", sort=False).groups.items():
        history = df.loc[indices].set_index("timestamp")["fill_level_pct"]
        rolling = history.rolling("6h", closed="left", min_periods=3).mean()
        df.loc[indices, "rolling_mean_6h"] = rolling.to_numpy()

    return df
