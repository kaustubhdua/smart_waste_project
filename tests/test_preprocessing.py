import unittest

import pandas as pd

from person1_preprocessing import preprocess_data


def make_rows(times, values, bin_id="BIN_001"):
    return [
        {
            "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(hours=hour),
            "bin_id": bin_id,
            "latitude": 28.5,
            "longitude": 77.3,
            "capacity_liters": 200,
            "criticality": "Medium",
            "fill_level_pct": fill,
            "temperature_c": 25,
        }
        for hour, fill in zip(times, values)
    ]


class PreprocessingTests(unittest.TestCase):
    def test_historical_features_exclude_current_target_and_use_real_time_windows(self):
        rows = make_rows([0, 1, 2, 3], [10, 20, 30, 40])
        result = preprocess_data(pd.DataFrame(rows)).reset_index(drop=True)

        self.assertTrue(pd.isna(result.loc[0, "fill_lag_1h"]))
        self.assertTrue(pd.isna(result.loc[0, "fill_lag_3h"]))
        self.assertTrue(pd.isna(result.loc[0, "rolling_mean_6h"]))
        self.assertEqual(result.loc[1, "fill_lag_1h"], 10)
        self.assertTrue(pd.isna(result.loc[1, "fill_lag_3h"]))
        self.assertTrue(pd.isna(result.loc[1, "rolling_mean_6h"]))
        self.assertEqual(result.loc[3, "fill_lag_1h"], 30)
        self.assertEqual(result.loc[3, "fill_lag_3h"], 10)
        self.assertEqual(result.loc[3, "rolling_mean_6h"], 20)

    def test_lags_are_missing_when_observation_cadence_does_not_match_hours(self):
        rows = make_rows([0, 1, 5, 6, 7, 8, 9], [10, 20, 30, 40, 50, 60, 70])
        result = preprocess_data(pd.DataFrame(rows)).reset_index(drop=True)
        self.assertTrue(pd.isna(result.loc[2, "fill_lag_1h"]))
        self.assertTrue(pd.isna(result.loc[2, "fill_lag_3h"]))
        self.assertEqual(result.loc[3, "fill_lag_1h"], 30)
        self.assertTrue(pd.isna(result.loc[3, "fill_lag_3h"]))

    def test_features_do_not_cross_bin_boundaries(self):
        rows = make_rows([0, 1], [10, 20], "BIN_001") + make_rows([0, 1], [90, 95], "BIN_002")
        result = preprocess_data(pd.DataFrame(rows))
        second_bin = result[result["bin_id"] == "BIN_002"].reset_index(drop=True)
        self.assertTrue(pd.isna(second_bin.loc[0, "fill_lag_1h"]))
        self.assertEqual(second_bin.loc[1, "fill_lag_1h"], 90)

    def test_duplicate_bin_timestamps_are_rejected(self):
        rows = make_rows([0, 1], [10, 20])
        rows.append(rows[0].copy())
        with self.assertRaisesRegex(ValueError, "duplicate timestamps"):
            preprocess_data(pd.DataFrame(rows))

    def test_out_of_range_fill_is_rejected_instead_of_clipped(self):
        rows = make_rows([0, 1, 2, 3], [10, 20, 30, 110])
        with self.assertRaisesRegex(ValueError, "between 0 and 100"):
            preprocess_data(pd.DataFrame(rows))

    def test_invalid_capacity_and_coordinates_are_rejected(self):
        rows = make_rows([0, 1], [10, 20])
        rows[0]["capacity_liters"] = 0
        with self.assertRaisesRegex(ValueError, "capacity_liters"):
            preprocess_data(pd.DataFrame(rows))
        rows = make_rows([0, 1], [10, 20])
        rows[0]["latitude"] = 95
        with self.assertRaisesRegex(ValueError, "latitude"):
            preprocess_data(pd.DataFrame(rows))


if __name__ == "__main__":
    unittest.main()
