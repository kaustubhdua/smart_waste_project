import unittest

from person3_fuzzy_logic import (
    FuzzyPrioritySystem,
    calculate_priority,
    create_fuzzy_system,
)


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.system = create_fuzzy_system()

    def test_score_is_bounded_for_edge_and_typical_inputs(self):
        for fill in (-100, 0, 50, 100, 200):
            score = calculate_priority(fill, 12, "High", self.system)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_non_finite_inputs_are_rejected(self):
        for values in (
            (float("nan"), 0, "Low"),
            (50, float("inf"), "Medium"),
            (50, 12, float("nan")),
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    calculate_priority(*values)

    def test_criticality_changes_score(self):
        self.assertGreater(
            calculate_priority(80, 12, "High", self.system),
            calculate_priority(80, 12, "Low", self.system),
        )

    def test_fill_level_increases_priority(self):
        scores = [calculate_priority(fill, 24, 3, self.system) for fill in range(0, 101, 5)]
        self.assertEqual(scores, sorted(scores))

    def test_time_since_emptying_increases_priority(self):
        scores = [calculate_priority(65, hours, 3, self.system) for hours in range(0, 73, 3)]
        self.assertEqual(scores, sorted(scores))

    def test_numeric_and_linguistic_criticality_are_equivalent(self):
        self.assertEqual(
            calculate_priority(70, 30, 3, self.system),
            calculate_priority(70, 30, "Medium", self.system),
        )

    def test_membership_interpolation_is_continuous_at_boundaries(self):
        before = calculate_priority(54.9, 20, 3, self.system)
        at = calculate_priority(55, 20, 3, self.system)
        after = calculate_priority(55.1, 20, 3, self.system)
        self.assertLess(abs(at - before), 1.0)
        self.assertLess(abs(after - at), 1.0)

    def test_factory_returns_reusable_fuzzy_system(self):
        self.assertIsInstance(self.system, FuzzyPrioritySystem)
        self.assertEqual(
            self.system.score(80, 30, 5),
            calculate_priority(80, 30, "High", self.system),
        )

    def test_invalid_criticality_is_rejected(self):
        for value in (0, 6, "urgent"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    calculate_priority(50, 12, value, self.system)


if __name__ == "__main__":
    unittest.main()
