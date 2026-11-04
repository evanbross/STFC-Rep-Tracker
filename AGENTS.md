# AGENTS.md — STFC Rep Tracker

Agent configuration for AI coding assistants (Codex, Gemini, Qwen, etc.).

## Standards Files — Read These First

At session start, read this file and every standards file listed below before making changes.

**Stack standards (all agents):**
- `../Dev-Standards/COMMON_CODING_STANDARDS.md`
- `../Dev-Standards/PYTHON_STANDARDS.md`
- `../Dev-Standards/DATABASE_STANDARDS.md`
- `../Dev-Standards/FLASK_STANDARDS.md`
- `../Dev-Standards/GOOGLE_CODING_STANDARDS.md`
- `../Dev-Standards/JAVASCRIPT_TYPESCRIPT_STANDARDS.md`
- `../Dev-Standards/REACT_STANDARDS.md`
- `../Dev-Standards/INFRASTRUCTURE_STANDARDS.md`
- `../Dev-Standards/WINDOWS_STANDARDS.md`

**Agent-specific standards (read your own):**
- Codex → `../Dev-Standards/CODEX_CODING_STANDARDS.md`
- Gemini → `../Dev-Standards/GEMINI_CODING_STANDARDS.md`
- Qwen → `../Dev-Standards/QWEN_CODING_STANDARDS.md`

**Not applicable to this project:**
- `FASTAPI_STANDARDS.md` — backend is Flask, not FastAPI
- `TESTING_STANDARDS.md` — no automated test suite

## Project Overview

STFC Rep Tracker reads Star Trek Fleet Command faction reputation values from the game window
via OCR (OpenCV + EasyOCR) and stores them in PostgreSQL. It consists of:

- **Flask REST API** (`main.py`, `app/`) — runs on port 7300 (override with `PORT`; `launcher.py` picks the next free port from 7300), requires Windows admin
- **React SPA** (`frontend/`) — Vite dev server on port 5173, proxies `/api` to Flask
- **Screen capture** (`app/screen_processing/`) — Windows-only; uses PyAutoGUI, PyGetWindow, win32api

## Running the App

```bash
# Backend (repo root, .venv active, run as admin)
python main.py

# Frontend dev server
cd frontend && npm run dev

# Production frontend build (served by Flask from frontend/dist)
cd frontend && npm run build
```

## Architecture Notes

These are the non-obvious patterns an agent is most likely to get wrong:

**Dynamic DAO loading** — Reputation DAOs are not imported statically. At startup, the
`factions` table is queried and each row's `reputation_table_name` / `reputation_dao_name`
columns determine which Python module and class to load. Adding a new reputation type
requires both a new `*_reputations_dao.py` file AND a DB row update — code alone is not
enough.

**Database singleton** — `Database` in `app/database/database.py` is the single hub passed
to all views via `current_app.config["DATABASE"]`. Never import DAO classes directly in
views; always go through the `Database` instance.

**Blueprint prefix convention** — every Blueprint is registered with a `/api/<noun>` prefix
in `main.py`. View files use relative route strings (e.g. `@bp.route("/<id>")`), not full
paths.

**Template images** — CV template images live in `app/screen_snippets/`. The
`faction_selected_snippets` table maps factions to multiple templates per type (`button` |
`desc`). The `snippet_unselected` column on `factions` holds a single filename for the
unselected sidebar button.

**Windows-only runtime** — screen capture code calls `win32api`, `PyGetWindow`, and
`PyAutoGUI`. These imports will fail on Linux/Mac. Do not introduce platform-agnostic
abstractions unless the user asks.

**Admin elevation** — `main.py` auto-relaunches itself elevated on Windows if not already
running as admin. Do not remove or bypass this check.
