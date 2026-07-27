import unittest
from pathlib import Path

import pandas as pd

from dashboard_core import EXPECTED_COLUMNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class PublicBuildTests(unittest.TestCase):
    def test_demo_data_is_explicitly_fictional(self) -> None:
        demo_path = PROJECT_ROOT / "data" / "project_tracker_demo.csv"
        projects = pd.read_csv(demo_path)

        self.assertGreaterEqual(len(projects), 10)
        self.assertEqual(projects.columns.tolist(), EXPECTED_COLUMNS)
        self.assertTrue(projects["Project ID"].str.startswith("DEMO-").all())
        self.assertTrue(projects["Notes"].eq("Fictional portfolio record.").all())

    def test_private_sheet_is_not_hardcoded(self) -> None:
        app_source = (PROJECT_ROOT / "streamlit_app.py").read_text(encoding="utf-8")

        self.assertNotIn("SHEET_URL =", app_source)
        self.assertFalse(
            (PROJECT_ROOT / "data" / "project_tracker_snapshot.csv").exists()
        )


if __name__ == "__main__":
    unittest.main()
