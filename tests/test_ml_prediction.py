import tempfile
import unittest
import joblib
from pathlib import Path
import pandas as pd
from person1_preprocessing import generate_synthetic_bin_data, preprocess_data
from person2_ml_prediction import train_ml_model, load_ml_model, predict_next_fill

class PredictionTests(unittest.TestCase):
    def test_train_save_load_and_predict(self):
        raw = generate_synthetic_bin_data(num_bins=3, days=5, seed=7)
        frame = preprocess_data(raw)
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "data.csv"
            artifact = Path(tmp) / "model.pkl"
            frame.to_csv(csv, index=False)
            model = train_ml_model(str(csv), str(artifact))
            saved = joblib.load(artifact)
            self.assertEqual(saved["feature_schema_version"], 2)
            self.assertEqual(saved["metrics"]["target_interval_minutes"], [30, 90])
            self.assertGreater(saved["metrics"]["train_rows"], 0)
            loaded = load_ml_model(str(artifact))
            latest = frame.sort_values(["bin_id", "timestamp"]).groupby("bin_id").tail(1)
            predictions = predict_next_fill(loaded, latest)
            self.assertEqual(len(predictions), 3)
            self.assertTrue(((predictions >= 0) & (predictions <= 100)).all())


    def test_training_rejects_two_hour_next_observation_intervals(self):
        raw = generate_synthetic_bin_data(num_bins=3, days=5, seed=9)
        frame = preprocess_data(raw)
        for _, indices in frame.groupby("bin_id").groups.items():
            start = frame.loc[indices[0], "timestamp"]
            frame.loc[indices, "timestamp"] = pd.date_range(
                start=start, periods=len(indices), freq="2h"
            )
        with tempfile.TemporaryDirectory() as tmp:
            csv = Path(tmp) / "irregular.csv"
            artifact = Path(tmp) / "model.pkl"
            frame.to_csv(csv, index=False)
            with self.assertRaisesRegex(ValueError, "30–90 minute"):
                train_ml_model(str(csv), str(artifact))

    def test_prediction_rejects_non_finite_feature_values(self):
        class FakeModel:
            def predict(self, rows):
                raise AssertionError("Model must not receive invalid features")

        rows = pd.DataFrame([{feature: 1.0 for feature in [
            "capacity_liters", "temperature_c", "hour", "day_of_week",
            "is_weekend", "fill_lag_1h", "fill_lag_3h", "rolling_mean_6h",
        ]}])
        rows.loc[0, "fill_lag_3h"] = float("nan")
        with self.assertRaisesRegex(ValueError, "non-finite"):
            predict_next_fill(FakeModel(), rows)

if __name__ == "__main__":
    unittest.main()
