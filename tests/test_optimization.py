import unittest

from person4_optimization import solve_vrp


class RouteOptimizationTests(unittest.TestCase):
    def test_empty_input_returns_no_routes(self):
        self.assertEqual(solve_vrp([]), {})

    def test_invalid_vehicle_count_is_rejected(self):
        with self.assertRaises(ValueError):
            solve_vrp([], num_vehicles=0)

    def test_invalid_coordinates_are_rejected(self):
        with self.assertRaises(ValueError):
            solve_vrp([{"latitude": 200, "longitude": 77.3, "waste_volume": 10}])

    def test_demand_over_capacity_is_rejected(self):
        with self.assertRaises(ValueError):
            solve_vrp([{"latitude": 28.5, "longitude": 77.3, "waste_volume": 1200}], vehicle_capacity=1000)

    def test_heterogeneous_vehicle_capacities_are_respected(self):
        bins = [
            {"latitude": 28.5410, "longitude": 77.3950, "waste_volume": 800},
            {"latitude": 28.5290, "longitude": 77.3880, "waste_volume": 500},
        ]
        routes = solve_vrp(bins, num_vehicles=2, vehicle_capacity=[600, 1000])
        self.assertEqual(len(routes), 2)
        capacities = [600, 1000]
        for index, route in enumerate(routes.values()):
            self.assertLessEqual(route["total_load"], capacities[index])

    def test_heterogeneous_capacity_count_must_match_fleet(self):
        with self.assertRaisesRegex(ValueError, "match num_vehicles"):
            solve_vrp([], num_vehicles=2, vehicle_capacity=[500])

    def test_heterogeneous_capacities_must_be_positive_and_finite(self):
        with self.assertRaisesRegex(ValueError, "positive finite"):
            solve_vrp([], num_vehicles=2, vehicle_capacity=[500, 0])


if __name__ == "__main__":
    unittest.main()
