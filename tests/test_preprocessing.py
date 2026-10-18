import unittest

import pandas as pd

from person1_preprocessing import preprocess_data


class PreprocessingTests(unittest.TestCase):
    def test_historical_features_exclude_current_target(self):
        rows = []
        for bin_id, values in (("BIN_001", [10, 20, 30, 40]), ("BIN_002", [70, 80, 90, 95])):
            for hour, fill in enumerate(values):
                rows.append(
                    {
                        "timestamp": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=hour),
                        "bin_id": bin_id,
                        "latitude": 28.5,
                        "longitude": 77.3,
                        "capacity_liters": 200,
                        "criticality": "Medium",
                        "fill_level_pct": fill,
                        "temperature_c": 25,
                    }
                )

        result = preprocess_data(pd.DataFrame(rows))
        first_bin = result[result["bin_id"] == "BIN_001"].reset_index(drop=True)

        self.assertTrue(pd.isna(first_bin.loc[0, "fill_lag_1h"]))
        self.assertTrue(pd.isna(first_bin.loc[0, "fill_lag_3h"]))
        self.assertTrue(pd.isna(first_bin.loc[0, "rolling_mean_6h"]))
        self.assertTrue(pd.isna(first_bin.loc[1, "fill_lag_3h"]))
        self.assertEqual(first_bin.loc[1, "fill_lag_1h"], 10)
        self.assertEqual(first_bin.loc[3, "fill_lag_3h"], 10)
        self.assertEqual(first_bin.loc[1, "rolling_mean_6h"], 10)
        self.assertEqual(first_bin.loc[2, "rolling_mean_6h"], 15)
        self.assertEqual(first_bin.loc[2, "rolling_mean_6h"], (10 + 20) / 2)

    def test_features_do_not_cross_bin_boundaries(self):
        rows = []
        for bin_id, values in (("BIN_001", [10, 20]), ("BIN_002", [90, 95])):
            for hour, fill in enumerate(values):
                rows.append(
                    {
                        "timestamp": pd.Timestamp("2026-01-01") + pd.Timedelta(hours=hour),
                        "bin_id": bin_id,
                        "latitude": 28.5,
                        "longitude": 77.3,
                        "capacity_liters": 200,
                        "criticality": "Medium",
                        "fill_level_pct": fill,
                        "temperature_c": 25,
                    }
                )

        result = preprocess_data(pd.DataFrame(rows))
        second_bin = result[result["bin_id"] == "BIN_002"].reset_index(drop=True)
        self.assertTrue(pd.isna(second_bin.loc[0, "fill_lag_1h"]))
        self.assertEqual(second_bin.loc[1, "fill_lag_1h"], 90)
        self.assertEqual(second_bin.loc[1, "rolling_mean_6h"], 90)


if __name__ == "__main__":
    unittest.main()
