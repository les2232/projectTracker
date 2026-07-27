# ProjectTracker

ProjectTracker is a privacy-aware Streamlit dashboard for managing a portfolio
of projects from one Google Sheet. It turns a detailed tracker into a practical
command center with portfolio metrics, prioritization, follow-up dates, filters,
charts, and project-level detail.

> **Public portfolio note:** This repository contains fictional demo records
> only. Spreadsheet URLs, credentials, and real project data are intentionally
> excluded.

## Highlights

- KPI cards for total, open, active, blocked, attention, due-soon, and complete
  projects
- interactive filters across area, status, priority, and attention
- full-text project search
- status and portfolio-area visualizations
- a deterministic focus queue ranked by attention, priority, and follow-up date
- upcoming follow-ups and individual project detail
- filtered CSV export
- private Google Sheets support through Streamlit secrets
- automatic fallback to useful fictional demo data

## Architecture

```text
Private Google Sheet
        │
        ▼
Streamlit GSheets connection ── unavailable ──► Fictional demo CSV
        │                                      (public-safe fallback)
        └──────────────────┬───────────────────┘
                           ▼
               normalization and ranking
                           ▼
                 interactive dashboard
```

The live integration is read-only. The Google Sheet remains the source of
truth, while the dashboard caches reads for up to 60 seconds and offers a
manual refresh control.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run streamlit_app.py
```

Without secrets, the app starts immediately in demo mode.

## Connect a private Google Sheet

1. Enable the Google Sheets API in a Google Cloud project.
2. Create a service account with read-only access.
3. Share the Sheet with the service account email as **Viewer**.
4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
5. Replace every placeholder with the service-account values and Sheet URL.
6. Restart Streamlit.

The Sheet should contain a worksheet named `Project Tracker` with these
columns:

```text
Project ID, Project, Area, Status, Priority, Attention, Current State,
Latest Milestone, Next Action, Blocker / Dependency, Known Deadline / Event,
Suggested Follow-Up, Last Reviewed, Notes
```

Never commit `.streamlit/secrets.toml`; it is excluded by `.gitignore`.

## Test

```bash
python -m unittest discover -s tests -v
```

## Deploy

On Streamlit Community Cloud, select `streamlit_app.py` as the entrypoint and
add the real `secrets.toml` values through the app's Secrets settings. Keep a
deployment private when it connects to confidential project data.
