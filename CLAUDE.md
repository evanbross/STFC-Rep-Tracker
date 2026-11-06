@../Dev-Standards/COMMON_CODING_STANDARDS.md
@../Dev-Standards/PYTHON_STANDARDS.md
@../Dev-Standards/DATABASE_STANDARDS.md
@../Dev-Standards/JAVASCRIPT_TYPESCRIPT_STANDARDS.md
@../Dev-Standards/REACT_STANDARDS.md
@../Dev-Standards/INFRASTRUCTURE_STANDARDS.md
@../Dev-Standards/WINDOWS_STANDARDS.md
@../Dev-Standards/FLASK_STANDARDS.md
@../Dev-Standards/GOOGLE_CODING_STANDARDS.md
@../Dev-Standards/TESTING_STANDARDS.md

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

STFC Rep Tracker is a Star Trek Fleet Command reputation tracking tool. It consists of:

- A **Flask REST API** (Python) that stores faction reputation data in PostgreSQL
- A **React SPA** (Vite) for viewing and managing reputation history
- An **OCR screen capture module** that reads reputation values directly from the STFC game window using OpenCV +
  EasyOCR

## Running the App

**Backend** (from repo root, with `.venv` active):

```bash
python main.py
# Runs on http://localhost:7300 by default (override with the PORT env var)
# Note: requires admin privileges on Windows (main.py auto-relaunches elevated if needed)
```

Normally the backend is started via `launcher.py` instead of `main.py` directly. The launcher picks
a free port starting at 7300 and registers it with the shared `../infra` Caddy instance as
`http://stfc.localhost` (app name `"stfc"`, overridable via `CADDY_APP_NAME`) — see `launcher.py`
and `../infra/caddy_registry.py`. If Caddy isn't running, the launcher falls back to opening
`http://localhost:<port>` directly.

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

**Environment**: `config.py` defines `AppSettings` (pydantic-settings). It is the one place environment variables
are read: `FLASK_ENV` (`development` | `production` | `testing`, default `development`), `SECRET_KEY`,
`DATABASE_URL_POOLED` / `DIRECT`, `CORS_ORIGINS`, `CADDY_APP_NAME`, `PORT`, `DISABLE_CAPTURE`.
- `main.py` builds it once with `load_settings()` and passes it to `create_app(settings)`. Importing `main` builds
  nothing: `python main.py` runs `_serve()` (lock → elevation → env check → app → listeners → OCR warm-up), and
  Gunicorn/tests call the `create_wsgi_app()` factory (`main:create_wsgi_app()`).
- In production, a missing, placeholder, or short (<16 chars) `SECRET_KEY` stops startup.
- Settings errors name the field, never the value.
- Add new env vars to `AppSettings`; don't call `os.environ.get` elsewhere.

**Runtime settings**: Controlled by `settings.yaml` at the project root (screen wait retries, delays, OCR scale,
template match thresholds, etc.). Accessed via `capture_cfg()` in `app/app_config.py`.
- The file is UTF-8 and must parse. A file that exists but is broken stops startup; a missing one means defaults.
- The app writes it only through `_add_combat_template` (combat template lists). That re-reads the file under a lock,
  re-parses the edit and checks that only that list changed, then swaps the file in atomically, keeping comments and
  CRLF line endings.

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

- Pure-function tests (`tests/test_ocr_text.py`, `test_target_math.py`, `test_app_config.py`) need nothing.
- API contract tests (marked `db`) need `DATABASE_URL_TEST` in `.env`, pointing at a disposable **Neon branch**,
  never the live database. Each run creates its own empty schema in that branch, runs the real Flask app against
  it, and drops it afterwards. Without the variable those tests are skipped, and `-rs` prints why.
- `tests/conftest.py` overwrites `DATABASE_URL_POOLED`/`DIRECT` before the app is imported and refuses a test URL
  on the same Neon endpoint as production, so pytest cannot reach the live DB.
- `xfail(strict=True)` tests record known bugs scheduled in `docs/remediation-plan-2026-11-03.md`. When a fix
  lands they XPASS and fail the run. Remove the marker in the same change.
- Pure OCR parsers live in `app/screen_processing/ocr_text.py` and target maths in `target_math.py`, so they can
  be tested without importing EasyOCR/OpenCV.

## Architecture

### Backend (Flask)

`main.py` is the entry point. It checks for admin elevation (required for window activation), creates the Flask app,
initializes the `Database` singleton, registers Blueprints, and serves the React frontend from `frontend/dist` as a
catch-all.

**Database layer** (`app/database/`):

- `database.py` — `Database` class is the central hub. Holds `factions_dao` (aliased as `.factions`),
  `status_entries_dao` (aliased as `.status_entries`), and `selected_snippets_dao` (aliased as `.selected_snippets`).
  Passed to views via `app.config["DATABASE"]`.
- `factions_dao.py` — CRUD for the `factions` table. `get_faction_summary()` computes deltas, change rates, and
  reputation levels by joining with `status_entries` and calling the appropriate `ReputationsDAO`.
- `status_entries_dao.py` — Stores time-series reputation readings. The `value_delta` column exists in the schema but is
  not populated.
- `faction_selected_snippets_dao.py` — Maps factions to multiple template image filenames with a `snippet_type` ('
  button' | 'desc' | NULL). Used for detecting selected faction state during screen capture.
- `reputations_dao.py` — Base `ReputationsDAO` class. Subclasses are **dynamically loaded at startup** based on data in
  the `factions` table: `faction.reputation_table_name` → Python module name, `faction.reputation_dao_name` → class
  name. Adding a new reputation type requires: (1) a new `*_reputations_dao.py` file, and (2) the faction row in the DB
  to reference it.

**Reputation DAOs** (all in `app/database/`, all inherit from `ReputationsDAO`):

- `fkr_reputations_dao.py` — `FKRReputationsDAO` (19 tiers, Enemy → Champion)
- `augment_reputations_dao.py` — `AugmentReputationsDAO` (6 tiers)
- `rogue_reputations_dao.py` — `RogueReputationsDAO` (9 tiers)
- `bajoran_reputations_dao.py` — `BajoranReputationsDAO`
- `terran_reputations_dao.py` — `TerranReputationsDAO` (10 tiers)
- `dti_reputations_dao.py` — `DTIReputationsDAO`
- `section31_reputations_dao.py` — `Section31ReputationsDAO`
- `ex_borg_reputations_dao.py` — `ExBorgReputationsDAO`

**Cross-origin write guard** (`app/request_guards.py`): a `before_request` hook on both Flask apps (main and the
7443 community-mod listener) returns 403 for POST/PUT/PATCH/DELETE under `/api/` when `Origin` (or `Referer`) is
neither the app's own origin nor in `CORS_ORIGINS`. Requests with neither header (curl, the community mod) pass.
New origins that serve the UI must be added to `CORS_ORIGINS`. The 7443 listener binds to
`community_mod.bind_host` in `settings.yaml` (default `127.0.0.1`).

**Request bodies and errors**:
- JSON bodies are parsed with `parse_body(Model)` (`app/views/validation.py`) against the Pydantic models in
  `app/views/request_models.py`. A bad body becomes a 400 `{"error", "fields"}` that never echoes the input.
- DAOs raise `NotFoundError` / `ConflictError` (`app/domain_errors.py`). App-level handlers map them to 404 / 409,
  and any other exception to a generic 500 with the traceback logged.
- Routes don't need their own `try/except Exception`.

**Views** (`app/views/`): Flask Blueprints. Each retrieves the DB via `current_app.config["DATABASE"]`. Blueprints are
registered in `main.py` with URL prefixes:

| Blueprint file           | URL prefix            |
|--------------------------|-----------------------|
| `factions_view.py`       | `/api/factions`       |
| `status_entries_view.py` | `/api/status_entries` |
| `reputations_view.py`    | `/api/reputations`    |
| `capture_screen_view.py` | `/api/capture-screen` |
| `system_view.py`         | `/api/system`         |

Key endpoints:

- `GET  /api/factions/summary` — faction list with current value, delta, change rate, rep level, minutes to goal (
  sortable)
- `GET  /api/factions/<id>/selected-snippets` — snippet images for a faction
- `POST /api/factions/<id>/selected-snippets` — upload a new snippet image (multipart: `file`, `filename`,
  `snippet_type`)
- `DELETE /api/factions/selected-snippets/<snippet_id>`
- `GET  /api/factions/snippet-image/<filename>` — serve snippet image from disk
- `POST /api/capture-screen/reputations` — trigger full reputation capture run
- `POST /api/capture-screen/identify-faction` — identify which faction is currently highlighted
- `GET  /api/reputations/all` — all reputation tiers grouped by table
- `GET  /api/reputations/by-table/<table_name>`

API docs (Flasgger/Swagger UI) available at `/apidocs`.

**Screen capture** (`app/screen_processing/`):

- `screen_capture.py` — `ScreenCapture` singleton. Finds/activates the STFC game window (PyGetWindow/win32api), captures
  screenshots via PyAutoGUI, and provides template matching helpers.
  `capture_window(window, delay=None, activate=False)` — set `activate=True` only on the first capture; polling loops
  leave it False to avoid the 1s activation sleep.
- `process_reputations.py` — `ProcessReputationsOrchestrator`. For each faction: waits for the unselected button
  template, clicks it, waits for the selected/desc confirm template, then runs EasyOCR on the top-left points region.
  Also contains `capture_and_identify_faction()` for single-shot faction identification.
- `process_away_teams.py` — `AwayTeamOrchestrator`. Navigates to the Away Teams screen and collects mission results.
- `process_gifts.py` — `GiftsOrchestrator`. Placeholder for gifts screen capture.
- `process_event_rewards.py` — `EventRewardsOrchestrator`. Placeholder for event rewards capture.

### Frontend (React + Vite)

`frontend/src/App.jsx` defines routes:

- `/` → `Dashboard.jsx` — main tracker view with faction stats table and history chart (Chart.js)
- `/factions` → `Factions.jsx` — faction CRUD with snippet image management modal
- `/reputations` → `Reputations.jsx` — reputation tier viewer

During development, Vite proxies `/api/*` to `http://127.0.0.1:7300`. In production, Flask serves
`frontend/dist/index.html` for all non-API routes.

### Key Faction Data Model

The `factions` table drives most dynamic behavior:

- `name`, `code`, `color` — Display fields
- `reputation_table_name` — PostgreSQL table name and Python module suffix (e.g., `fkr_reputations` →
  `app/database/fkr_reputations_dao.py`)
- `reputation_dao_name` — Python class name to instantiate (e.g., `FKRReputationsDAO`)
- `display_order` — Controls order in UI
- `on_chart` — Whether to include in the history chart
- `snippet_unselected` — Template filename for the faction's unselected sidebar button
- `snippet_selected_button` — Template filename for the selected button state (legacy single-image field)

The `faction_selected_snippets` table maps each faction to multiple template images:

- `snippet_type`: `'button'` (selected button highlight) or `'desc'` (selected detail panel) or NULL
- Multiple snippets per type are supported per faction
- Managed via the Snippets modal in `Factions.jsx`; auto-pasted filenames follow `Selected-<type>-<CODE>-<N>.png`

## Best Practices

When modifying code, follow established best practices for the language and framework in use. This includes (but is not limited to):

- SOLID principles and clean architecture
- Proper separation of concerns
- Secure coding patterns (no injection risks, no overly broad exception catches, validate at boundaries)
- Idiomatic use of the language and framework — prefer stdlib/framework features over hand-rolled solutions
- Consistent naming and style conventions already present in the codebase
- **OAuth / interactive auth flows must never be triggered from background API calls.** If a token is missing or invalid during a non-auth endpoint, raise an error and return it to the caller — never open a browser window or start a local callback server mid-request. Interactive auth flows belong exclusively in dedicated auth endpoints (e.g. `POST /auth`, `GET /login`) that the user explicitly invokes.

allowedTools "Edit,Write,Read,Glob,Grep,Agent,Bash(npm run build),Bash(npm run dev)"
