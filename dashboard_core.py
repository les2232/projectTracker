from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta

import pandas as pd


EXPECTED_COLUMNS = [
    "Project ID",
    "Project",
    "Area",
    "Status",
    "Priority",
    "Attention",
    "Current State",
    "Latest Milestone",
    "Next Action",
    "Blocker / Dependency",
    "Known Deadline / Event",
    "Suggested Follow-Up",
    "Last Reviewed",
    "Notes",
]

DATE_COLUMNS = [
    "Known Deadline / Event",
    "Suggested Follow-Up",
    "Last Reviewed",
]

ATTENTION_ORDER = {
    "Unblock": 1,
    "Due now": 2,
    "Follow up": 3,
    "This week": 4,
    "No date": 5,
    "Later": 6,
    "Closed": 99,
}

PRIORITY_ORDER = {
    "High": 1,
    "Medium": 2,
    "Low": 3,
}


def _derive_attention(row: pd.Series, today: pd.Timestamp) -> str:
    status = str(row.get("Status", "") or "").strip()
    if status == "Complete":
        return "Closed"
    if status == "Blocked":
        return "Unblock"
    if status == "Waiting":
        return "Follow up"

    follow_up = row.get("Suggested Follow-Up")
    if pd.isna(follow_up):
        return "No date"
    if follow_up <= today:
        return "Due now"
    if follow_up <= today + timedelta(days=7):
        return "This week"
    return "Later"


def normalize_projects(
    frame: pd.DataFrame | None,
    *,
    today: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Return a predictable, typed project table."""
    if frame is None:
        frame = pd.DataFrame()

    projects = frame.copy()
    projects.columns = [str(column).strip() for column in projects.columns]
    projects = projects.loc[:, ~projects.columns.str.startswith("Unnamed:")]

    for column in EXPECTED_COLUMNS:
        if column not in projects.columns:
            projects[column] = pd.NA

    projects = projects[EXPECTED_COLUMNS]

    for column in DATE_COLUMNS:
        projects[column] = pd.to_datetime(projects[column], errors="coerce")

    text_columns = [
        column for column in EXPECTED_COLUMNS if column not in DATE_COLUMNS
    ]
    for column in text_columns:
        projects[column] = projects[column].astype("string").fillna("").str.strip()

    projects = projects[
        projects["Project ID"].ne("") | projects["Project"].ne("")
    ].reset_index(drop=True)

    resolved_today = (
        pd.Timestamp(today).normalize()
        if today is not None
        else pd.Timestamp.today().normalize()
    )
    missing_attention = projects["Attention"].eq("")
    if missing_attention.any():
        projects.loc[missing_attention, "Attention"] = projects.loc[
            missing_attention
        ].apply(_derive_attention, axis=1, today=resolved_today)

    return projects


def filter_projects(
    projects: pd.DataFrame,
    *,
    areas: Iterable[str] | None = None,
    statuses: Iterable[str] | None = None,
    priorities: Iterable[str] | None = None,
    attention: Iterable[str] | None = None,
    search: str = "",
) -> pd.DataFrame:
    filtered = projects.copy()

    selections = {
        "Area": list(areas or []),
        "Status": list(statuses or []),
        "Priority": list(priorities or []),
        "Attention": list(attention or []),
    }
    for column, selected in selections.items():
        if selected:
            filtered = filtered[filtered[column].isin(selected)]

    query = search.strip()
    if query:
        searchable = (
            filtered[
                [
                    "Project ID",
                    "Project",
                    "Area",
                    "Current State",
                    "Next Action",
                    "Notes",
                ]
            ]
            .fillna("")
            .astype(str)
            .agg(" ".join, axis=1)
        )
        filtered = filtered[searchable.str.contains(query, case=False, na=False)]

    return filtered.reset_index(drop=True)


def compute_metrics(projects: pd.DataFrame) -> dict[str, int | float]:
    total = int(len(projects))
    complete = int(projects["Status"].eq("Complete").sum())
    return {
        "total": total,
        "open": total - complete,
        "active": int(projects["Status"].eq("Active").sum()),
        "blocked": int(projects["Status"].eq("Blocked").sum()),
        "needs_attention": int(
            projects["Attention"].isin(["Unblock", "Follow up", "Due now"]).sum()
        ),
        "due_soon": int(
            projects["Attention"].isin(["Due now", "This week"]).sum()
        ),
        "complete": complete,
        "completion_rate": (complete / total) if total else 0.0,
    }


def build_focus_queue(projects: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if projects.empty:
        return projects.copy()

    queue = projects[projects["Status"].ne("Complete")].copy()
    queue["_attention_rank"] = (
        queue["Attention"].map(ATTENTION_ORDER).fillna(50).astype(int)
    )
    queue["_priority_rank"] = (
        queue["Priority"].map(PRIORITY_ORDER).fillna(50).astype(int)
    )
    queue["_follow_up_rank"] = queue["Suggested Follow-Up"].fillna(
        pd.Timestamp.max.normalize()
    )

    queue = queue.sort_values(
        ["_attention_rank", "_priority_rank", "_follow_up_rank", "Project"],
        kind="stable",
    )
    return queue.drop(
        columns=["_attention_rank", "_priority_rank", "_follow_up_rank"]
    ).head(limit)


def count_by(projects: pd.DataFrame, column: str) -> pd.DataFrame:
    if projects.empty:
        return pd.DataFrame(columns=[column, "Count"])

    summary = (
        projects[column]
        .replace("", "Unspecified")
        .value_counts(dropna=False)
        .rename_axis(column)
        .reset_index(name="Count")
    )
    return summary


def upcoming_follow_ups(
    projects: pd.DataFrame,
    *,
    today: pd.Timestamp | None = None,
    days: int = 14,
) -> pd.DataFrame:
    resolved_today = (
        pd.Timestamp(today).normalize()
        if today is not None
        else pd.Timestamp.today().normalize()
    )
    end = resolved_today + timedelta(days=days)

    mask = (
        projects["Status"].ne("Complete")
        & projects["Suggested Follow-Up"].notna()
        & projects["Suggested Follow-Up"].between(
            resolved_today, end, inclusive="both"
        )
    )
    return projects.loc[mask].sort_values(
        ["Suggested Follow-Up", "Priority", "Project"], kind="stable"
    )
