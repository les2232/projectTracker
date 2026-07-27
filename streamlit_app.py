from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from streamlit_gsheets import GSheetsConnection

from dashboard_core import (
    build_focus_queue,
    compute_metrics,
    count_by,
    filter_projects,
    normalize_projects,
    upcoming_follow_ups,
)


APP_DIR = Path(__file__).resolve().parent
DEMO_DATA_PATH = APP_DIR / "data" / "project_tracker_demo.csv"
WORKSHEET = "Project Tracker"

STATUS_COLORS = {
    "Active": "#2563EB",
    "Blocked": "#DC2626",
    "Waiting": "#7C3AED",
    "Planning": "#0F766E",
    "Paused": "#64748B",
    "Complete": "#16A34A",
    "Unspecified": "#CBD5E1",
}


st.set_page_config(
    page_title="Project Portfolio Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            --navy: #0f172a;
            --slate: #475569;
            --muted: #64748b;
            --teal: #0f766e;
            --surface: #ffffff;
            --canvas: #f6f8fb;
            --border: #e2e8f0;
        }

        .stApp { background: var(--canvas); }
        .block-container {
            max-width: 1500px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid var(--border);
        }
        .hero {
            background:
                radial-gradient(circle at 84% 18%, rgba(20, 184, 166, .28), transparent 26%),
                linear-gradient(135deg, #0f172a 0%, #16243d 58%, #0f3e46 100%);
            border-radius: 22px;
            color: #ffffff;
            padding: 1.55rem 1.75rem;
            margin-bottom: 1.15rem;
            box-shadow: 0 18px 45px rgba(15, 23, 42, .16);
        }
        .hero-kicker {
            color: #99f6e4;
            font-size: .75rem;
            font-weight: 800;
            letter-spacing: .13em;
            margin-bottom: .35rem;
            text-transform: uppercase;
        }
        .hero h1 {
            color: #ffffff;
            font-size: clamp(1.85rem, 3vw, 2.65rem);
            letter-spacing: -.035em;
            line-height: 1.05;
            margin: 0;
        }
        .hero p {
            color: #cbd5e1;
            font-size: 1rem;
            margin: .55rem 0 0;
            max-width: 850px;
        }
        .source-pill {
            align-items: center;
            background: rgba(255, 255, 255, .1);
            border: 1px solid rgba(255, 255, 255, .18);
            border-radius: 999px;
            color: #e2e8f0;
            display: inline-flex;
            font-size: .75rem;
            font-weight: 700;
            gap: .45rem;
            margin-top: .9rem;
            padding: .36rem .7rem;
        }
        .source-dot {
            background: #2dd4bf;
            border-radius: 999px;
            box-shadow: 0 0 0 4px rgba(45, 212, 191, .13);
            height: .5rem;
            width: .5rem;
        }
        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-top: 4px solid var(--accent);
            border-radius: 15px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, .06);
            min-height: 104px;
            padding: .95rem 1rem .8rem;
        }
        .metric-label {
            color: var(--muted);
            font-size: .72rem;
            font-weight: 800;
            letter-spacing: .055em;
            text-transform: uppercase;
        }
        .metric-value {
            color: var(--navy);
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -.035em;
            line-height: 1.1;
            margin-top: .32rem;
        }
        .section-title {
            color: var(--navy);
            font-size: 1.2rem;
            font-weight: 800;
            letter-spacing: -.018em;
            margin: .35rem 0 .15rem;
        }
        .section-copy {
            color: var(--muted);
            font-size: .88rem;
            margin-bottom: .75rem;
        }
        [data-testid="stPlotlyChart"],
        [data-testid="stDataFrame"] {
            background: #ffffff;
            border: 1px solid var(--border);
            border-radius: 16px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, .045);
            overflow: hidden;
        }
        div[data-testid="stExpander"] {
            background: #ffffff;
            border-color: var(--border);
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def configured_sheet_url() -> str:
    """Read the private spreadsheet URL without hardcoding it in source."""
    try:
        return str(st.secrets["connections"]["gsheets"]["spreadsheet"]).strip()
    except Exception:
        return ""


def load_demo_projects() -> pd.DataFrame:
    """Load fictional portfolio data and keep its follow-up dates useful."""
    projects = normalize_projects(pd.read_csv(DEMO_DATA_PATH))
    today = pd.Timestamp.today().normalize()
    follow_up_offsets = {
        "Due now": 0,
        "Unblock": 1,
        "Follow up": 3,
        "This week": 5,
        "Later": 21,
    }
    for attention, offset in follow_up_offsets.items():
        projects.loc[
            projects["Attention"].eq(attention),
            "Suggested Follow-Up",
        ] = today + timedelta(days=offset)
    return projects


def load_projects(sheet_url: str) -> tuple[pd.DataFrame, bool, str]:
    if sheet_url:
        try:
            connection = st.connection("gsheets", type=GSheetsConnection)
            frame = connection.read(
                spreadsheet=sheet_url,
                worksheet=WORKSHEET,
                ttl=60,
            )
            return normalize_projects(frame), True, "Live Google Sheet"
        except Exception:
            pass

    return load_demo_projects(), False, "Fictional demo data"


def metric_card(label: str, value: str | int, accent: str) -> None:
    st.markdown(
        f"""
        <div class="metric-card" style="--accent:{accent}">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_date(value: object) -> str:
    if pd.isna(value):
        return "None"
    timestamp = pd.Timestamp(value)
    return f"{timestamp.strftime('%b')} {timestamp.day}, {timestamp.year}"


def format_loaded_at(value: datetime) -> str:
    time_text = value.strftime("%I:%M %p").lstrip("0")
    timezone_text = value.tzname() or "local time"
    return (
        f"{value.strftime('%b')} {value.day}, {value.year} "
        f"at {time_text} {timezone_text}"
    )


def status_figure(projects: pd.DataFrame) -> go.Figure:
    summary = count_by(projects, "Status")
    colors = [STATUS_COLORS.get(status, "#94A3B8") for status in summary["Status"]]
    figure = go.Figure(
        go.Pie(
            labels=summary["Status"],
            values=summary["Count"],
            hole=0.62,
            marker={"colors": colors, "line": {"color": "#FFFFFF", "width": 2}},
            textinfo="label+value",
            hovertemplate="<b>%{label}</b><br>%{value} projects<br>%{percent}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "Project status", "x": 0.05, "xanchor": "left"},
        annotations=[
            {
                "text": f"<b>{len(projects)}</b><br><span style='font-size:12px'>projects</span>",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"color": "#0F172A", "size": 20},
            }
        ],
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"family": "Arial", "color": "#334155"},
        legend={"orientation": "h", "y": -0.08, "x": 0},
        margin={"l": 18, "r": 18, "t": 62, "b": 45},
        height=390,
    )
    return figure


def area_figure(projects: pd.DataFrame) -> go.Figure:
    summary = count_by(projects, "Area").sort_values("Count", ascending=True)
    figure = go.Figure(
        go.Bar(
            x=summary["Count"],
            y=summary["Area"],
            orientation="h",
            marker={"color": "#0F766E", "line": {"color": "#115E59", "width": 0.6}},
            text=summary["Count"],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>%{x} projects<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": "Projects by area", "x": 0.04, "xanchor": "left"},
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font={"family": "Arial", "color": "#334155"},
        xaxis={
            "title": "",
            "showgrid": True,
            "gridcolor": "#E2E8F0",
            "zeroline": False,
            "dtick": 1,
        },
        yaxis={"title": "", "showgrid": False},
        margin={"l": 22, "r": 42, "t": 62, "b": 36},
        height=390,
    )
    return figure


def render_table(frame: pd.DataFrame, columns: list[str], height: int = 430) -> None:
    display = frame[columns].copy()
    st.dataframe(
        display,
        hide_index=True,
        width="stretch",
        height=height,
        column_config={
            "Project": st.column_config.TextColumn("Project", width="medium"),
            "Current State": st.column_config.TextColumn(
                "Current State", width="large"
            ),
            "Next Action": st.column_config.TextColumn("Next Action", width="large"),
            "Blocker / Dependency": st.column_config.TextColumn(
                "Blocker / Dependency", width="large"
            ),
            "Suggested Follow-Up": st.column_config.DateColumn(
                "Follow-Up", format="MMM D, YYYY"
            ),
            "Known Deadline / Event": st.column_config.DateColumn(
                "Deadline / Event", format="MMM D, YYYY"
            ),
            "Last Reviewed": st.column_config.DateColumn(
                "Last Reviewed", format="MMM D, YYYY"
            ),
        },
    )


inject_styles()
sheet_url = configured_sheet_url()
projects, is_live, source_name = load_projects(sheet_url)
loaded_at = format_loaded_at(datetime.now(timezone.utc))

source_copy = (
    "Connected to the private Google Sheet"
    if is_live
    else "Using fictional demo data; private Sheet details stay in secrets"
)
st.markdown(
    f"""
    <div class="hero">
        <div class="hero-kicker">Project command center</div>
        <h1>Project Portfolio Dashboard</h1>
        <p>See what is moving, what is blocked, and what deserves attention next—without losing the detail in the tracker.</p>
        <div class="source-pill">
            <span class="source-dot"></span>
            {source_name} · {loaded_at}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Dashboard controls")
    st.caption(source_copy)

    if st.button("↻ Refresh data", width="stretch"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

    if sheet_url:
        st.link_button("Open Google Sheet", sheet_url, width="stretch")
    else:
        st.caption("The private Sheet link appears only after secrets are configured.")
    st.divider()

    search = st.text_input(
        "Search projects",
        placeholder="Name, state, next action…",
    )
    area_options = sorted(projects["Area"].dropna().loc[lambda s: s.ne("")].unique())
    status_options = sorted(
        projects["Status"].dropna().loc[lambda s: s.ne("")].unique()
    )
    priority_options = ["High", "Medium", "Low"]
    attention_options = [
        option
        for option in ["Unblock", "Due now", "Follow up", "This week", "No date", "Later", "Closed"]
        if option in projects["Attention"].unique()
    ]

    selected_areas = st.multiselect("Area", area_options)
    selected_statuses = st.multiselect("Status", status_options)
    selected_priorities = st.multiselect("Priority", priority_options)
    selected_attention = st.multiselect("Attention", attention_options)

filtered = filter_projects(
    projects,
    areas=selected_areas,
    statuses=selected_statuses,
    priorities=selected_priorities,
    attention=selected_attention,
    search=search,
)

if not is_live:
    st.info(
        "This public portfolio build uses fictional demo records. Add private "
        "Google Sheet credentials to switch the source badge to live data."
    )

if filtered.empty:
    st.warning("No projects match the current filters.")
    st.stop()

metrics = compute_metrics(filtered)
metric_specs = [
    ("Total", metrics["total"], "#2563EB"),
    ("Open", metrics["open"], "#0F766E"),
    ("Active", metrics["active"], "#4F46E5"),
    ("Blocked", metrics["blocked"], "#DC2626"),
    ("Needs attention", metrics["needs_attention"], "#D97706"),
    ("Due ≤ 7 days", metrics["due_soon"], "#7C3AED"),
    ("Complete", metrics["complete"], "#16A34A"),
]
metric_columns = st.columns(len(metric_specs))
for column, (label, value, accent) in zip(metric_columns, metric_specs):
    with column:
        metric_card(label, value, accent)

st.write("")
chart_left, chart_right = st.columns([0.9, 1.35], gap="large")
with chart_left:
    st.plotly_chart(status_figure(filtered), width="stretch", config={"displayModeBar": False})
with chart_right:
    st.plotly_chart(area_figure(filtered), width="stretch", config={"displayModeBar": False})

st.markdown('<div class="section-title">Priority focus queue</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="section-copy">Projects are ranked by attention state, priority, and follow-up date.</div>',
    unsafe_allow_html=True,
)
focus = build_focus_queue(filtered, limit=10)
render_table(
    focus,
    ["Project", "Status", "Priority", "Attention", "Next Action", "Suggested Follow-Up"],
    height=390,
)

tab_projects, tab_follow_ups, tab_details = st.tabs(
    ["All projects", "Upcoming follow-ups", "Project detail"]
)
with tab_projects:
    render_table(
        filtered,
        [
            "Project ID",
            "Project",
            "Area",
            "Status",
            "Priority",
            "Attention",
            "Current State",
            "Next Action",
            "Suggested Follow-Up",
        ],
        height=520,
    )
    csv_data = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered projects",
        data=csv_data,
        file_name="jay_project_portfolio_filtered.csv",
        mime="text/csv",
    )

with tab_follow_ups:
    follow_ups = upcoming_follow_ups(filtered, days=14)
    if follow_ups.empty:
        st.success("No follow-ups are scheduled in the next 14 days.")
    else:
        render_table(
            follow_ups,
            [
                "Project",
                "Status",
                "Priority",
                "Attention",
                "Suggested Follow-Up",
                "Next Action",
            ],
            height=430,
        )

with tab_details:
    selected_project = st.selectbox(
        "Choose a project",
        filtered["Project"].tolist(),
        label_visibility="collapsed",
    )
    project = filtered.loc[filtered["Project"].eq(selected_project)].iloc[0]
    detail_left, detail_right = st.columns([1.25, 1], gap="large")
    with detail_left:
        st.subheader(project["Project"])
        st.caption(
            f"{project['Project ID']} · {project['Area']} · "
            f"{project['Status']} · {project['Priority']} priority"
        )
        st.markdown("**Current state**")
        st.write(project["Current State"] or "No current-state note yet.")
        st.markdown("**Latest milestone**")
        st.write(project["Latest Milestone"] or "No milestone recorded yet.")
        st.markdown("**Next action**")
        st.info(project["Next Action"] or "No next action recorded yet.")
    with detail_right:
        st.markdown("**Blocker or dependency**")
        st.write(project["Blocker / Dependency"] or "None recorded.")
        st.markdown("**Known deadline or event**")
        deadline = project["Known Deadline / Event"]
        st.write(format_date(deadline))
        st.markdown("**Suggested follow-up**")
        follow_up = project["Suggested Follow-Up"]
        st.write(format_date(follow_up))
        st.markdown("**Notes**")
        st.write(project["Notes"] or "No additional notes.")
