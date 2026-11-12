import unittest

from streamlit.testing.v1 import AppTest


class WasteOpsStreamlitTests(unittest.TestCase):
    def test_every_workspace_page_renders(self):
        app = AppTest.from_file("app.py", default_timeout=45).run()
        self.assertFalse(app.exception, str(app.exception))

        for page in (
            "Overview",
            "Bin network",
            "Route planner",
            "Collection jobs",
            "Fleet",
            "Analytics",
        ):
            app.session_state["active_page"] = page
            app.run()
            self.assertFalse(app.exception, f"{page}: {app.exception}")

    def test_route_planner_builds_capacity_safe_vehicle_routes(self):
        app = AppTest.from_file("app.py", default_timeout=60).run()
        app.session_state["active_page"] = "Route planner"
        app.run()
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


if __name__ == "__main__":
    unittest.main()
