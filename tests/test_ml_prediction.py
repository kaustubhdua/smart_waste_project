import tempfile
import unittest
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
            loaded = load_ml_model(str(artifact))
            latest = frame.sort_values(["bin_id", "timestamp"]).groupby("bin_id").tail(1)
            predictions = predict_next_fill(loaded, latest)
            self.assertEqual(len(predictions), 3)
            self.assertTrue(((predictions >= 0) & (predictions <= 100)).all())

if __name__ == "__main__":
    unittest.main()
