import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class WasteOpsStreamlitTests(unittest.TestCase):
    def test_every_workspace_page_renders(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
        self.assertFalse(app.exception, str(app.exception))

        for page in (
            "Overview",
            "Bin network",
            "Route planner",
            "Collection jobs",
            "Fleet",
            "Analytics",
        ):
            app.radio[0].set_value(page).run()
            self.assertFalse(app.exception, f"{page}: {app.exception}")

    def test_route_planner_builds_capacity_safe_vehicle_routes(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        app.radio[0].set_value("Route planner").run()
        self.assertFalse(app.exception, str(app.exception))

        optimize = next(
            button for button in app.button
            if button.label == "✦  Optimize collection routes"
        )
        optimize.click().run()
        self.assertFalse(app.exception, str(app.exception))

        workspace = app.session_state["wasteops"]
        self.assertTrue(workspace["routes"], "Expected the default fleet to receive a feasible route plan.")
        for route in workspace["routes"].values():
            self.assertLessEqual(route["load_l"], route["capacity_l"])


    def test_workspace_starts_with_consistent_fleet_and_no_fake_history(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        self.assertFalse(app.exception, str(app.exception))
        workspace = app.session_state["wasteops"]
        self.assertEqual(workspace["events"], [])
        self.assertTrue(all(row["collected"] == 0 and row["requests"] == 0 for row in workspace["history"]))
        self.assertFalse(any(job["status"] == "Completed" for job in workspace["jobs"]))
        for job in workspace["jobs"]:
            vehicle = next(row for row in workspace["vehicles"] if row["id"] == job["vehicle"])
            self.assertFalse(vehicle["available"])
            self.assertIn(job["bin_id"], workspace["routes"][vehicle["id"]]["bins"])

    def test_active_vehicle_cannot_be_released(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        app.radio[0].set_value("Fleet").run()
        self.assertFalse(app.exception, str(app.exception))
        release = next(button for button in app.button if button.label == "Release")
        self.assertTrue(release.disabled)

    def test_training_cycle_advances_telemetry_and_opens_jobs(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60).run()
        self.assertFalse(app.exception, str(app.exception))
        before = app.session_state["wasteops"]
        previous_time = before["simulation_time"]
        previous_cycles = before["simulation_cycles"]
        previous_fills = {row["id"]: row["fill_pct"] for row in before["bins"]}
        advance = next(button for button in app.button if button.label == "▶  Advance operations")
        advance.click().run()
        self.assertFalse(app.exception, str(app.exception))
        after = app.session_state["wasteops"]
        self.assertEqual(after["simulation_cycles"], previous_cycles + 1)
        self.assertNotEqual(after["simulation_time"], previous_time)
        self.assertTrue(all(row["fill_pct"] >= previous_fills[row["id"]] for row in after["bins"]))
        self.assertTrue(after["telemetry_history"])
        self.assertTrue(any(job["status"] == "Detected" for job in after["jobs"]))

    def test_fuzzy_priority_is_bounded_and_monotonic_for_fill(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=45).run()
        self.assertFalse(app.exception, str(app.exception))
        from person3_fuzzy_logic import calculate_priority
        low = calculate_priority(20, 5, "Low")
        high = calculate_priority(90, 5, "Low")
        self.assertGreaterEqual(low, 0)
        self.assertLessEqual(high, 100)
        self.assertGreater(high, low)


if __name__ == "__main__":
    unittest.main()
