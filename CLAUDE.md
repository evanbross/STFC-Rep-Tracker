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
a free port starting at 7300, passes it as `PORT` with a random `LAUNCH_ID`, and waits until
`GET /api/health` echoes that ID (an open port alone could be another process), then opens the `url`
the backend reports.

The backend registers **itself** with the shared `../infra` Caddy instance as `http://stfc.localhost`
(app name `"stfc"`, overridable via `CADDY_APP_NAME`) once it has bound its port, however it was started
(launcher, PyCharm, `python main.py`) — see `app/caddy_route.py`. A `RouteReconciler` puts the route back
if Caddy restarts or starts late, and a clean exit removes it; the launcher removes it after terminating
the backend, since `TerminateProcess` skips that cleanup. The client comes from the `zt-common` package
(`../infra/zt-common`), an editable uv **dev** dependency. It's optional: if it isn't installed (the shipped
app exports with `--no-dev`) or Caddy isn't running, the app is reached at `http://localhost:<port>`.

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
`DATABASE_URL_POOLED` / `DIRECT`, `CORS_ORIGINS`, `CADDY_APP_NAME`, `PORT`, `DISABLE_CAPTURE`,
`COMMUNITY_MOD_TOKEN`, `LAUNCH_ID` (set by the launcher only).
- `main.py` builds it once with `load_settings()` and passes it to `create_app(settings)`. Importing `main` builds
  nothing: `python main.py` runs `_serve()` (lock → elevation → env check → app → OCR warm-up → serve), and
  tests call the `create_wsgi_app()` factory. `DISABLE_CAPTURE` keeps the Windows capture stack out (tests set it).
- In production, a missing, placeholder, or short (<16 chars) `SECRET_KEY` stops startup.
- Settings errors name the field, never the value.
- Add new env vars to `AppSettings`; don't call `os.environ.get` elsewhere.

**Runtime settings**: Controlled by `settings.yaml` at the project root (screen wait retries, delays, OCR scale,
template match thresholds, etc.). Accessed via `capture_cfg()` in `app/app_config.py`.
- The file is UTF-8 and must parse. A file that exists but is broken stops startup; a missing one means defaults.
- The app writes it only through `_add_combat_template` (combat template lists). That re-reads the file under a lock,
  re-parses the edit and checks that only that list changed, then swaps the file in atomically, keeping comments and
  CRLF line endings.

**File locations** (`app/paths.py`, a leaf module): `runtime_dir()` is writable and survives reinstalls (the exe folder
when frozen). `resource_dir()` holds bundled read-only files (PyInstaller `_internal`). In a source checkout both are
the project root.
- Resolve files with `runtime_path()` / `resource_path()`. Don't compute paths from `__file__` or the cwd.
- Snippets go through `app/snippet_store.py`. Lookups check the user folder first, then the bundled one. New snippets
  are always written to the user folder (`new_snippet_path`), so upgrades don't wipe them.
- Screenshots go to `app_config.screenshots_dir()`. Any new writer there calls `screenshot_retention.notify_written()`
  after saving; that wakes the pruner, which keeps the newest 30 files (subfolders like `debug/` are left alone).
- Elevation and single-instance mutexes live in `app/win_process.py`, shared by `launcher.py` and `main.py`.

**Dependencies**: Python 3.14 (`.python-version`, `requires-python`). `pyproject.toml` + `uv.lock`
are the source of truth. After changing a dependency, run `uv lock`, then regenerate `requirements.txt` with the
`uv export` command in its header. Never edit `requirements.txt` by hand. There is no Docker deployment; the app ships
only through the Windows installer.
- Don't move to 3.15 yet: `scikit-image` (via easyocr) has no 3.15 Windows wheel before 0.27, and `pyyaml` /
  `pyclipper` only build from source there.
- Changing `.python-version` can make an IDE's uv integration rebuild `.venv` on its own. Close the IDE, or point
  `UV_PROJECT_ENVIRONMENT` at a scratch folder, before trying a different version.
- The Inno installer (`installer/`) bundles embedded Python 3.14.7. `PYTHON_VER` in `prepare.bat` and `PythonVer`
  in `STFC_Rep_Tracker.iss` must match each other and `.python-version`'s major.minor. Its torch/torchvision pins
  come from `requirements.txt` (`prepare.bat` writes `requirements_torch.txt` with the CPU builds).

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest
```

- Pure-function tests (`tests/test_ocr_text.py`, `test_target_math.py`, `test_territory_parsing.py`,
  `test_system_targets_parsing.py`, `test_spocks_club_parsing.py`, `test_app_config.py`) need nothing.
- `tests/test_territory_fixture.py` runs real template matching on `tests/fixtures/territory_page.jpg`, a real
  capture, against the snippets in `app/screen_snippets`. If you re-capture a territory snippet, check it still
  passes. It needs the Windows capture packages, but not OCR.
- API contract tests (marked `db`) need `DATABASE_URL_TEST` in `.env`, pointing at a disposable **Neon branch**,
  never the live database. Each run creates its own empty schema in that branch, runs the real Flask app against
  it, and drops it afterwards. Without the variable those tests are skipped, and `-rs` prints why.
- `tests/conftest.py` overwrites `DATABASE_URL_POOLED`/`DIRECT` before the app is imported and refuses a test URL
  on the same Neon endpoint as production, so pytest cannot reach the live DB.
- `xfail(strict=True)` tests record known bugs scheduled in `docs/remediation-plan-2026-11-03.md`. When a fix
  lands they XPASS and fail the run. Remove the marker in the same change.
- Pure logic lives apart from the capture stack, so it can be tested without EasyOCR, OpenCV or pyautogui:
  - `ocr_text.py`: text parsers and `confident_tokens`
  - `target_math.py`: tracking, intercept and scoring
  - `territory_parsing.py`: row strips and name/timer pairing
  - `system_targets_parsing.py`: crop regions and candidate bookkeeping
  - `app/spocks_club_parsing.py`: reading a Spock's Club export (no capture stack at all)

  New `*_parsing.py` functions take tunables as arguments; the `process_*.py` callers read `capture_cfg`.

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
- `status_entries_dao.py` — Stores time-series reputation readings. `timestamp` is `timestamptz`; the API serializes it
  as ISO 8601 in UTC (`iso_utc`).
- `migrations.py` — Ordered schema migrations recorded in `schema_version`, run by `init_database` under an advisory
  lock in one transaction. Never edit a shipped migration; append a new one. DDL lives here, not in the DAOs.
- `faction_selected_snippets_dao.py` — Maps factions to multiple template image filenames with a `snippet_type` ('
  button' | 'desc' | NULL). Used for detecting selected faction state during screen capture.
- `reputations_dao.py` — Base `ReputationsDAO` class. Every `app/database/<table>_reputations_dao.py` file is one
  reputation type: `available_implementations()` scans them, one DAO per file is registered at startup, and its tier
  table is created and seeded whenever its `get_initial_reputations()` rows change (`reputation_seed` fingerprints).
  Adding a reputation type is just a new file; factions pick it in the UI (`GET /api/reputations/types`) and work
  without a restart. Tier rows are cached in memory and refreshed by `update_row`.

**Reputation DAOs** (all in `app/database/`, all inherit from `ReputationsDAO`):

- `fkr_reputations_dao.py` — `FKRReputationsDAO` (19 tiers, Enemy → Champion)
- `augment_reputations_dao.py` — `AugmentReputationsDAO` (6 tiers)
- `rogue_reputations_dao.py` — `RogueReputationsDAO` (9 tiers)
- `bajoran_reputations_dao.py` — `BajoranReputationsDAO`
- `terran_reputations_dao.py` — `TerranReputationsDAO` (10 tiers)
- `dti_reputations_dao.py` — `DTIReputationsDAO`
- `section31_reputations_dao.py` — `Section31ReputationsDAO`
- `ex_borg_reputations_dao.py` — `ExBorgReputationsDAO`

**Cross-origin write guard** (`app/request_guards.py`): a `before_request` hook returns 403 for
POST/PUT/PATCH/DELETE under `/api/` when `Origin` (or `Referer`) is neither the app's own origin nor in
`CORS_ORIGINS`. Requests with neither header (curl, the community mod) pass. New origins that serve the UI must be
added to `CORS_ORIGINS`.

**Community mod sync**: the STFC community mod posts to `http://stfc.localhost/api/community-mod/` (a
`[sync.targets.stfc-rep-tracker]` table in the game's `community_patch_settings.toml`), which Caddy proxies to the
main app on whatever port it picked. Payloads are appended to `community-data.jsonl`. Then each `resource` record
(`app/community_mod_parsing.py`) whose `rid` matches a faction's `spocks_resource_id` is saved as a status entry
at the receive time, but only if it differs from that faction's latest entry (`add_changed_entries_at`); the
mod resends unchanged values, and a full sync has ~5,700 resources. When `COMMUNITY_MOD_TOKEN`
is set, a request whose `stfc-sync-token` header doesn't match gets 401 before its body is read; unset, any
caller is accepted (fine while only this machine can reach it). `GET /api/community-mod/status` returns the last
capture time (the capture file's mtime), and `GET /api/community-mod/events` is an SSE stream with a `capture`
event per payload and a `readings` event when one saved values; the Dashboard's `CommunityModStatus` reads both,
and a `readings` event (or a reconnect) reloads the cards and chart. There is no separate listener
or fixed port; an installed build without Caddy doesn't receive mod sync.

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
| `target_types_view.py`   | `/api/target-types`   |
| `territory_view.py`      | `/api/territory`      |
| `calendar_view.py`       | `/api/calendar`       |
| `community_mod_view.py`  | `/api/community-mod`  |
| `spocks_club_view.py`    | `/api/spocks-club`    |
| `health_view.py`         | `/api/health`         |

Key endpoints:

- `GET  /api/factions/summary` — faction list with current value, delta, change rate, rep level, minutes to goal (
  sortable)
- `GET  /api/factions/<code>/selected-snippets` — snippet images for a faction
- `POST /api/factions/<code>/selected-snippets` — upload a new snippet image (multipart: `file`, `filename`,
  `snippet_type`)
- `DELETE /api/factions/selected-snippets/<snippet_id>`
- `GET  /api/factions/snippet-image/<filename>` — serve snippet image from disk
- `POST /api/capture-screen/reputations` — trigger full reputation capture run
- `POST /api/capture-screen/identify-faction` — identify which faction is currently highlighted
- `GET  /api/reputations/all` — all reputation tiers grouped by table
- `GET  /api/reputations/by-table/<table_name>`
- `POST /api/spocks-club/preview` — read an uploaded Spock's Club export (multipart: `file`, optional
  `last_modified` ms) and return each mapped faction's value, unmatched factions, and the reading time
- `POST /api/spocks-club/import` — save previewed readings at one `exported_at`; a faction that already has a
  reading at that exact instant is skipped, so re-importing a file adds nothing

API docs (Flasgger/Swagger UI) available at `/apidocs`.

**Screen capture** (`app/screen_processing/`):

- `screen_capture.py` — `ScreenCapture` singleton. Finds/activates the STFC game window (PyGetWindow/win32api), captures
  screenshots via PyAutoGUI, and provides template matching helpers.
  `capture_window(window, delay=None, activate=False)` — set `activate=True` only on the first capture; polling loops
  leave it False to avoid the 1s activation sleep.
- Orchestrators subclass `BaseOrchestrator` (`base_orchestrator.py`), which holds `self.sc` and `_activate()`.
  - They return only success payloads. On failure they raise a `capture_errors.py` class: `CaptureError` (500),
    `CaptureTargetNotFound` / `GameWindowNotFound` (404), or `CaptureRequestError` (400).
  - `capture_screen_view._run_capture` maps exception types to status codes under the automation lock. Don't return
    `{"error": ...}` dicts, and don't match on message text.
  - Messages are shown to the user, so write them as instructions.
- `process_reputations.py` — `ProcessReputationsOrchestrator`. For each faction: waits for the unselected button
  template, clicks it, waits for the selected/desc confirm template, then runs EasyOCR on the top-left points region.
  `IdentifyFactionOrchestrator` does single-shot faction identification.
- `process_away_teams.py` — `AwayTeamOrchestrator`. Navigates to the Away Teams screen and collects mission results.
- `process_gifts.py` — `GiftsOrchestrator`. Navigates to Gifts and claims everything.
- `process_event_rewards.py` — `EventRewardsOrchestrator`. Placeholder: raises `NotImplementedError` (501), and its
  Dashboard button is disabled.

### Frontend (React + Vite)

`frontend/src/App.jsx` defines routes:

- `/` → `Dashboard.jsx` — composes `FactionCards`, `CaptureToolbar`, `TerritoryScheduleModal` and `HistoryChart`, and
  owns only their reload order (`refreshAll`: cards, then chart)
- `/factions` → `Factions.jsx` — faction CRUD with snippet image management modal
- `/reputations` → `Reputations.jsx` — reputation tier viewer
- `/system-targets` → `SystemTargets.jsx` — classify hostile types, scan, and attack
- `/combat` → `Combat.jsx` — continuous scan/refresh loop with attack

Conventions:
- Every request goes through `src/api/client.js` (`api`, `errorMessage(err, fallback)`). It's the only axios importer;
  `useCaptureBusy`'s interceptors sit on that instance. Capture errors arrive as non-2xx responses, so don't check
  `data.error` on success.
- One folder per component under `src/components/` (jsx, its hook, helpers, `index.js`); import from the folder.
- `npm run lint` (ESLint 10 + React Hooks rules) must report no errors; it catches undefined names on runtime-only
  branches that `npm run build` misses. No `React` default import: the JSX runtime is automatic.
- `npm test` (Vitest + Testing Library, jsdom) runs `*.test.js(x)` next to the code they cover. HTTP goes through
  `fakeApi()` in `src/test/fakeApi.js`, which swaps the shared instance's adapter so the real interceptors (capture
  timeout, `useCaptureBusy`) still run. Don't mock `api.get`/`api.post` directly. These tests check frontend logic
  against the response shapes it expects; the backend's `db` contract tests check those shapes against Flask.

During development, Vite proxies `/api/*` to the port in `.backend-port` (written by `main.py` on startup in a source
checkout; 7300 if absent). It reads the file once, so restart `npm run dev` if the backend moves ports. In production, Flask serves
`frontend/dist/index.html` for all non-API routes.

### Key Faction Data Model

The `factions` table drives most dynamic behavior:

- `name`, `code`, `color` — Display fields
- `reputation_table_name` — PostgreSQL table name and Python module suffix (e.g., `fkr_reputations` →
  `app/database/fkr_reputations_dao.py`); validated against the available implementations
- `reputation_dao_name` — Class name of that implementation (e.g., `FKRReputationsDAO`); filled in by the API from the table
- `display_order` — Controls order in UI
- `on_chart` — Whether the faction's series is shown when the history chart loads. Every faction is in the legend
  either way, and clicking an entry shows or hides it until the page reloads
- `snippet_unselected` — Template filename for the faction's unselected sidebar button
- `snippet_selected_button` — Template filename for the selected button state (legacy single-image field)
- `spocks_resource_id` — `EntityId` of the faction's reputation resource in a Spock's Club export (e.g.
  970475396 = "Federation Points"). Matched by ID because names repeat in the export. Unique when set; NULL means
  the faction is skipped by imports (Maverick has no resource in the export)

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
