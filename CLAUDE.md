# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

STFC Rep Tracker is a Star Trek Fleet Command reputation tracking tool. It consists of:
- A **Flask REST API** (Python) that stores faction reputation data in SQLite
- A **React SPA** (Vite) for viewing and managing reputation history
- An **OCR screen capture module** that reads reputation values directly from the STFC game window using OpenCV + EasyOCR

## Running the App

**Backend** (from repo root, with `.venv` active):
```bash
python main.py
# Runs on http://localhost:5000
```

**Frontend dev server** (proxies `/api` to Flask):
```bash
cd frontend
npm run dev
# Runs on http://localhost:5173
```

**Build frontend for production** (Flask serves from `frontend/dist`):
```bash
cd frontend
npm run build
```

**Environment**: Controlled by `FLASK_ENV` env var (`development` | `production` | `testing`). Defaults to `development`. See `config.py` for settings.

**External dependency**: EasyOCR (bundled Python package) is used for screen capture OCR. No separate binary installation required.

## Architecture

### Backend (Flask)

`main.py` is the entry point. It creates the Flask app, initializes the `Database` singleton, registers Blueprints, and serves the React frontend from `frontend/dist` as a catch-all.

**Database layer** (`app/database/`):
- `database.py` — `Database` class is the central hub. It holds `factions_dao` (also aliased as `.factions`) and `status_entries_dao` (aliased as `.status_entries`). Passed to handlers via `app.config["DATABASE"]`.
- `factions_dao.py` — CRUD for the `factions` table, plus the `get_faction_summary()` method which computes deltas, change rates, and reputation levels by joining with `status_entries` and calling the appropriate `ReputationsDAO`.
- `status_entries_dao.py` — Stores time-series reputation readings. The `value_delta` column exists in the schema but is not populated (that calculation code is commented out).
- `reputations_dao.py` — Base `ReputationsDAO` class. Subclasses (e.g., `FkrReputationsDAO`, `AugmentReputationsDAO`) are **dynamically loaded at startup** based on data in the `factions` table: `faction.reputation_table_name` → Python module name, `faction.reputation_dao_name` → class name. This means adding a new reputation type requires: (1) a new `*_dao.py` file, and (2) the faction row in the DB to reference it.

**Handlers** (`app/handlers/`): Flask Blueprints. Each handler retrieves the DB via `current_app.config["DATABASE"]`. Blueprints are registered in `main.py` with URL prefixes:
- `/api/factions` → `factions_handler.py`
- `/api/status_entries` → `status_entries_handler.py`
- `/api/reputations` → `reputations_handler.py`
- `/api/capture-screen` → `capture_handler.py`
- `/api/system` → `system_handler.py`

API docs (Flasgger/Swagger UI) available at `/apidocs`.

**Screen capture** (`app/screen_processing/`):
- `screen_capture.py` — Finds and activates the STFC game window (PyGetWindow/PyAutoGUI), navigates to the Faction Store, captures screenshots to `Screenshots/`. Initializes the EasyOCR reader (lazy singleton).
- `process_reputations.py` — Analyzes screenshots: uses brightness comparison across rows to detect the highlighted faction, and EasyOCR to read the points number.
- `process_away_teams.py`, `process_gifts.py`, `process_event_rewards.py` — Additional screen processors.

### Frontend (React + Vite)

`frontend/src/App.jsx` defines routes:
- `/` → `Dashboard.jsx` (main tracker view with history chart)
- `/factions` → `Factions.jsx` (faction management CRUD)
- `/reputations` → `Reputations.jsx` (reputation tier viewer)

During development, Vite proxies `/api/*` to `http://127.0.0.1:5000`. In production, Flask serves `frontend/dist/index.html` for all non-API routes.

### Key Faction Data Model

The `factions` table drives most of the dynamic behavior:
- `name`, `code`, `color` — Display fields
- `reputation_table_name` — SQLite table name and Python module suffix (e.g., `fkr_reputations` → `app/database/fkr_reputations_dao.py`)
- `reputation_dao_name` — Python class name to instantiate (e.g., `FkrReputationsDAO`)
- `display_order` — Controls order in UI
- `on_chart` — Whether to include in the history chart