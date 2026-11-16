import unittest
from datetime import datetime

from wasteops_operations import complete_collection, route_distance_for_bins


class CollectionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.stamp = datetime(2026, 11, 17, 1, 0)
        self.bins = [
            {"id": "BIN-001", "latitude": 28.54, "longitude": 77.39,
             "capacity_l": 1000, "fill_pct": 70.0, "battery_pct": 90,
             "temperature_c": 28.0, "status": "Attention"},
            {"id": "BIN-002", "latitude": 28.55, "longitude": 77.40,
             "capacity_l": 1000, "fill_pct": 30.0, "battery_pct": 88,
             "temperature_c": 29.0, "status": "Normal"},
        ]
        self.vehicles = [
            {"id": "TRK-01", "available": False, "latitude": 28.54,
             "longitude": 77.39, "route_progress_pct": 45.0}
        ]
        self.jobs = [
            {"id": "JOB-1", "bin_id": "BIN-001", "status": "Completed", "vehicle": "TRK-01"},
            {"id": "JOB-2", "bin_id": "BIN-002", "status": "In progress", "vehicle": "TRK-01"},
        ]
        self.data = {
            "history": [{"time": "01:00", "collected": 0, "requests": 0}],
            "telemetry_history": [],
            "routes": {"TRK-01": {
                "bins": ["BIN-001", "BIN-002"], "load_l": 1000,
                "capacity_l": 1500, "distance_km": 2.0,
            }},
            "route_order": ["TRK-01"],
        }
        self.depot = (28.5355, 77.3910)

    def test_completion_updates_fill_telemetry_history_and_remaining_route(self):
        job = self.jobs[0]
        complete_collection(self.data, self.bins, self.vehicles, self.jobs, job, self.stamp, self.depot)

        self.assertEqual(self.bins[0]["fill_pct"], 0.0)
        self.assertEqual(self.bins[0]["status"], "Normal")
        self.assertEqual(self.data["history"][-1]["collected"], 1)
        self.assertEqual(self.data["telemetry_history"][-1]["bin_id"], "BIN-001")
        self.assertEqual(self.data["telemetry_history"][-1]["fill_pct"], 0.0)
        self.assertEqual(self.data["routes"]["TRK-01"]["bins"], ["BIN-002"])
        self.assertEqual(self.data["routes"]["TRK-01"]["load_l"], 300)
        self.assertGreater(self.data["routes"]["TRK-01"]["distance_km"], 0)
        self.assertFalse(self.vehicles[0]["available"])

    def test_last_completion_releases_vehicle_and_clears_route(self):
        first, second = self.jobs
        complete_collection(self.data, self.bins, self.vehicles, self.jobs, first, self.stamp, self.depot)
        second["status"] = "Completed"
        complete_collection(self.data, self.bins, self.vehicles, self.jobs, second, self.stamp, self.depot)

        self.assertTrue(self.vehicles[0]["available"])
        self.assertEqual(self.vehicles[0]["route_progress_pct"], 0.0)
        self.assertEqual((self.vehicles[0]["latitude"], self.vehicles[0]["longitude"]), self.depot)
        self.assertNotIn("TRK-01", self.data["routes"])
        self.assertEqual(self.data["history"][-1]["collected"], 2)
        self.assertEqual(len(self.data["telemetry_history"]), 2)

    def test_route_distance_includes_depot_return(self):
        distance = route_distance_for_bins(["BIN-001"], self.bins, self.depot)
        self.assertGreater(distance, 0)


if __name__ == "__main__":
    unittest.main()
