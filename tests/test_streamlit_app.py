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


if __name__ == "__main__":
    unittest.main()
