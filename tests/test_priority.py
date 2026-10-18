import unittest
from person3_fuzzy_logic import calculate_priority

class PriorityTests(unittest.TestCase):
    def test_score_is_bounded(self):
        for fill in (-100, 0, 50, 100, 200):
            score = calculate_priority(fill, 12, "High")
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_non_finite_values_rejected(self):
        with self.assertRaises(ValueError):
            calculate_priority(float("nan"), 0, "Low")

    def test_criticality_changes_score(self):
        self.assertGreater(calculate_priority(80, 12, "High"), calculate_priority(80, 12, "Low"))

if __name__ == "__main__":
    unittest.main()
