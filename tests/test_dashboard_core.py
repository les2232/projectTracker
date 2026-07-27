import unittest

import pandas as pd

from dashboard_core import (
    build_focus_queue,
    compute_metrics,
    filter_projects,
    normalize_projects,
    upcoming_follow_ups,
)


class DashboardCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.today = pd.Timestamp("2026-07-26")
        self.projects = normalize_projects(
            pd.DataFrame(
                [
                    {
                        "Project ID": "P-001",
                        "Project": "Blocked build",
                        "Area": "Software & AI",
                        "Status": "Blocked",
                        "Priority": "High",
                        "Attention": "",
                        "Suggested Follow-Up": "2026-07-27",
                    },
                    {
                        "Project ID": "P-002",
                        "Project": "Waiting proposal",
                        "Area": "Career",
                        "Status": "Waiting",
                        "Priority": "Medium",
                        "Attention": "",
                        "Suggested Follow-Up": "2026-07-28",
                    },
                    {
                        "Project ID": "P-003",
                        "Project": "Active project",
                        "Area": "Software & AI",
                        "Status": "Active",
                        "Priority": "High",
                        "Attention": "",
                        "Suggested Follow-Up": "2026-07-29",
                    },
                    {
                        "Project ID": "P-004",
                        "Project": "Finished project",
                        "Area": "Work / IT",
                        "Status": "Complete",
                        "Priority": "Low",
                        "Attention": "",
                    },
                    {"Project ID": "", "Project": ""},
                ]
            ),
            today=self.today,
        )

    def test_normalize_types_and_derives_attention(self) -> None:
        self.assertEqual(len(self.projects), 4)
        self.assertEqual(self.projects.loc[0, "Attention"], "Unblock")
        self.assertEqual(self.projects.loc[1, "Attention"], "Follow up")
        self.assertEqual(self.projects.loc[2, "Attention"], "This week")
        self.assertEqual(self.projects.loc[3, "Attention"], "Closed")
        self.assertTrue(
            pd.api.types.is_datetime64_any_dtype(
                self.projects["Suggested Follow-Up"]
            )
        )

    def test_metrics(self) -> None:
        metrics = compute_metrics(self.projects)
        self.assertEqual(metrics["total"], 4)
        self.assertEqual(metrics["open"], 3)
        self.assertEqual(metrics["blocked"], 1)
        self.assertEqual(metrics["needs_attention"], 2)
        self.assertEqual(metrics["due_soon"], 1)
        self.assertEqual(metrics["complete"], 1)

    def test_focus_queue_orders_attention_before_priority(self) -> None:
        queue = build_focus_queue(self.projects)
        self.assertEqual(
            queue["Project"].tolist(),
            ["Blocked build", "Waiting proposal", "Active project"],
        )

    def test_filters_and_search(self) -> None:
        filtered = filter_projects(
            self.projects,
            areas=["Software & AI"],
            priorities=["High"],
            search="active",
        )
        self.assertEqual(filtered["Project"].tolist(), ["Active project"])

    def test_upcoming_follow_ups(self) -> None:
        follow_ups = upcoming_follow_ups(
            self.projects,
            today=self.today,
            days=2,
        )
        self.assertEqual(
            follow_ups["Project"].tolist(),
            ["Blocked build", "Waiting proposal"],
        )


if __name__ == "__main__":
    unittest.main()
