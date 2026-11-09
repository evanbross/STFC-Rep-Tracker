# STFC Rep Tracker — Remediation & Improvement Plan

**Date:** 2026-11-03
**Inputs:** `docs/full-project-review-2026-11-03.md`, plus a fresh pass over `main.py`, `config.py`,
`app/database/*`, `app/views/*`, `app/screen_processing/*`, `app/google_calendar.py`,
`app/app_config.py`, `launcher.py`, and the React pages.
**Status (2026-11-09):** Phases 0–5 are done, and so are the browser-check fixes N-B1 to N-B5. Still open:
building and installing the Inno installer on 3.14, then the snippet-across-reinstall check (Phase 5). Deferred:
N-T2 (a strict xfail that needs real OCR crops) and the N-T5 coverage gaps.

This document has three parts:

1. **Triage of the existing review.** Each finding gets a verdict (valid, partly valid, or
   re-rated), checked against the code, and a concrete fix.
2. **New findings** from this pass, grouped by organization/deduplication, user-facing speed,
   stability, and safety.
3. **A phased roadmap** that orders the work so each phase is small, testable, and leaves the
   app working.

---

## Part 1 — Triage of the 2026-11-03 review

The review is mostly accurate. Its severity ratings assume a networked, multi-user deployment.
In practice this is a single-user Windows tool whose normal launch path (`launcher.py` → `main.py`
→ `app.run()`) binds to `127.0.0.1`. Some ratings are adjusted to match that. A few findings
also missed something, or overstated something, when checked against the code.

| # | Review finding | Verdict | Adjusted severity |
|---|---|---|---|
| R1 | Production `SECRET_KEY` is a `property` object | **Valid bug, low impact today** | Low |
| R2 | Unauthenticated endpoints on non-loopback listeners | **Partly valid, and the real risk is a different one** | High (re-scoped) |
| R3 | Community payload size bypass + concurrent append corruption | **Valid** | Medium |
| R4 | No schema validation of request bodies | **Valid**, and it caused a real status-code bug (see N-S3) | Medium |
| R5 | Faction creation doesn't complete the dynamic-DAO lifecycle | **Valid** | Medium |
| R6 | No automated tests | **Valid** | High |
| R7 | Startup DDL used as a migration system | **Valid**, but full Alembic is overkill right now | Low |
| R8 | Port 7000 vs 7300 doc drift | **Valid, and `CLAUDE.md:142` has the same drift** | Low |
| R9 | No `.gitattributes` | **Valid** | Low |
| R10 | Stale logger names in `logging.yaml` | **Valid** | Low |
| R11 | Cleanup thread polls and can't be stopped | **Valid** | Low |
| R12 | Very large modules / components | **Valid** (detailed in Part 2) | Medium |
| R13 | Inconsistent type hints | **Valid** | Low |
| R14 | Large/misplaced tracked assets | **Valid** | Low |

### R1 — `SECRET_KEY` property

**Verified.** `ProductionConfig.SECRET_KEY` is an instance `@property` (`config.py:36-41`).
`flask_app.config.from_object(get_config())` passes the *class*, so Flask stores the descriptor
object and the "must be set" check never runs.

**Why it's Low rather than Critical:** nothing in the app uses `session`, `flash`, or signed
cookies. A grep for `session[`, `flash(`, and `SECRET_KEY` turns up only `config.py`. The bug
is real but has no effect yet.

**Plan:** replace `config.py` with a `pydantic-settings` `BaseSettings` class. The project
standards ask for this, and it also absorbs the scattered `os.environ.get()` calls in `main.py`
(`PORT`, `DISABLE_CAPTURE`, `DATABASE_URL_*`, `CADDY_APP_NAME`). `_check_env()` then becomes
model validation. Put a `model_validator` on the production profile that rejects an empty or
default secret. Add a regression test that sets `FLASK_ENV=production SECRET_KEY=abc` and
asserts `app.config["SECRET_KEY"] == "abc"`.

### R2 — Network exposure (re-scoped)

What's accurate and what isn't:

- **Overstated:** the review says the 7443 HTTPS listener can "initiate actions against the
  running game." It can't. `_run_community_mod_https_server` (`main.py:221-242`) registers
  *only* `community_mod_bp`, so its sole capability is appending to `community-data.json`.
  It does bind `0.0.0.0` (`main.py:239`) with unrestricted CORS (`main.py:233`). The community
  mod runs on the same machine, so `127.0.0.1` is enough.
- **Accurate:** Docker publishes `7300:7300` and Gunicorn binds `0.0.0.0`. Capture is disabled
  there, but every data-mutation route is reachable from the LAN.
- **Missed, and more important for the real deployment:** cross-site requests from the user's
  own browser. The main server only listens on loopback, but **any web page the user visits can
  POST to `http://localhost:7300`**. CORS controls whether the page can *read* the response.
  It does not stop the request from being sent. Two kinds of route are exposed:
  - **Body-less POSTs that drive the game:** `/api/capture-screen/reputations`, `/gifts`,
    `/away-team`, `/away-team-collect`, `/territory-capture`, `/system-targets/scan`. A plain
    cross-origin `<form method=post>` triggers them with no preflight.
  - **`request.get_json(force=True)` routes:** `factions_view.py:147,229`,
    `status_entries_view.py:98`, `community_mod_view.py:73`. `force=True` ignores
    `Content-Type`, so a cross-origin `text/plain` POST, which skips the preflight, gets parsed
    as JSON. An attacker page can create or rename factions and insert status entries.

**Plan (in order of value):**
1. Add one `before_request` guard on **both** Flask apps that rejects unsafe-method `/api/*`
   requests whose `Origin` (falling back to `Referer`) is neither the request's own host nor in
   `CORS_ORIGINS`, returning 403. This is the pattern prescribed by `FLASK_STANDARDS.md`
   § "CORS Is Not CSRF Protection". Put the decision in a plain function
   (`is_trusted_api_write_origin`) in a shared module so it can be unit-tested without Flask.
   Requests with neither header (curl, the test client, the community mod) pass through, since
   browsers always send `Origin` on cross-origin POSTs. The frontend needs no change.
2. Remove `force=True` everywhere. Pydantic parsing (R4) needs a real JSON body anyway.
3. Bind the 7443 listener to `127.0.0.1` and restrict its CORS. Make the bind address a setting
   (default loopback) so LAN use is an explicit opt-in.
4. Docker: publish `127.0.0.1:7300:7300` by default and document how to opt in to LAN access.
   Real authentication is only needed if LAN or remote access becomes an actual goal. Don't
   build it speculatively.

### R3 — Community payload

**Verified.** The `Content-Length` check (`community_mod_view.py:64-76`) is skipped for chunked
bodies, and neither Flask app sets `MAX_CONTENT_LENGTH`. The file write is three separate
`write` calls with no lock, and the same blueprint is mounted on two servers (`main.py:244, 283`).

**Plan:**
- Set `MAX_CONTENT_LENGTH` on both apps from the same `community_mod.max_payload_bytes`
  setting, so the limit isn't duplicated. Keep the explicit 413 for a clear error.
- Switch to JSON Lines: one `json.dumps(record) + "\n"`, written with a single `write()` while
  holding a module-level `threading.Lock`. That covers the Werkzeug threaded server, where both
  listeners run in one process. Docker/Gunicorn with 2 workers has no capture and no real
  community-mod use, so document that it's single-process only rather than adding a
  cross-process file lock.
- Rename the output to `community-data.jsonl`, update `.gitignore`, and add a one-time
  converter only if the old file actually matters.

### R4 — Request validation

**Valid.** Add `pydantic` (and `pydantic-settings` for R1) to `requirements.txt`,
`requirements-docker.txt`, and `pyproject.toml`. Build one small helper rather than
repeating try/except in every route:

```python
# app/views/_validation.py  (name without underscore if imported elsewhere)
def parse_body(model: type[T]) -> T  # raises a BadRequest carrying sanitized field errors
```

Register an `errorhandler` for that exception that returns
`{"error": "Invalid request", "fields": [...]}` with status 400. Models needed:
`FactionIn`, `StatusEntryIn`, `ReputationRowPatch`, `TerritorySystemIn` (with an `HH:MM`
pattern), `TargetPreferenceIn` (a `Literal` built from the single preference source, see
N-O4), `RefreshTargetsIn`, `AttackIn` (finite floats, coordinates bounded by window size),
and `TemplateCropIn` (positive `w/h`, `kind` as a `Literal`).

### R5 — Faction creation vs. dynamic DAOs

**Valid.** The frontend lets users type arbitrary `reputation_table_name` /
`reputation_dao_name` values, and the registry is only built at startup.

**Plan:** the set of valid reputation DAOs is fixed by the Python files that exist. Make that
the source of truth:
- Expose `ReputationsDAO.available_implementations()`, which scans
  `app/database/*_reputations_dao.py` once and returns `{table_name: class_name}`.
- Validate `FactionIn.reputation_table_name` / `reputation_dao_name` against it, and serve it at
  `GET /api/reputations/types` so the Factions form becomes a dropdown instead of two free-text
  fields.
- After a successful insert or update, call `ReputationsDAO.register_dao(name, dao)` (the DAO
  instance already exists if its table was created at startup) so the faction works without a
  restart. On a code/name rename, drop the stale registry key.

This also fixes a latent crash. `_compute_faction_status` falls back to
`ReputationsDAO(conn, reputation_table_name)` (`factions_dao.py:285`), which raises
`TypeError` when `reputation_table_name` is `None`.

### R6 — Tests

**Valid and the top priority.** Every other phase needs a safety net. Suggested layout:

- `tests/conftest.py`: a session-scoped Postgres. Prefer a disposable Neon branch or a local
  Docker `postgres:16` via `DATABASE_URL_TEST`, never the live DB. The app is created with
  `DISABLE_CAPTURE=1`.
- **Contract tests via the Flask test client against real Postgres:** factions CRUD (including
  a code rename cascading to `status_entries`), status-entry POST/GET, `/factions/summary`
  numbers on seeded data, reputation row PUT, territory CRUD, target-type preference, and the
  CSRF guard from R2.
- **Pure-function tests with no DB:** `_parse_time_remaining`, `_normalize_ocr_digits`,
  `_parse_name_level`, `_score_candidates`, `_match_and_track`, `_time_to_intercept`,
  `_extract_points` (against checked-in fixture crops), and `_add_combat_template` (against a
  temp `settings.yaml`).
- Windows UI-automation tests stay out of the default run (`-m windows` marker).

Add `TESTING_STANDARDS.md` to the `CLAUDE.md` includes once tests exist. The global rules
require it for projects with automated tests.

### R7 — Migrations

**Valid, but Alembic is premature** for a single-user DB that already does idempotent
`CREATE TABLE IF NOT EXISTS`. A lighter step fixes the actual pain points: startup cost and
unreviewable backfills.
- Add a `schema_version` table and an ordered list of `(version, sql)` migrations in
  `app/database/migrations.py`, run under the existing advisory lock.
- On startup, skip the work when the DB is already at head. This also speeds up startup (see
  N-P4): today every launch re-runs every `CREATE`, the snippet `UPDATE`, and around 120
  reputation-tier upserts across the remote Neon link.
- Move to Alembic only if a second deployment target or hand-written backfills show up.

### R8–R11 — Housekeeping (all valid)

- **R8:** fix `AGENTS.md:32` **and** `CLAUDE.md:142` (both say 7000; the real value is 7300).
- **R9:** add `.gitattributes` (`* text=auto eol=crlf`). Normalize in its own commit.
- **R10:** replace the `app.reputation_sucker.*` loggers with
  `app.screen_processing.process_reputations` / `.screen_capture`, and change the format to
  `%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s`.
- **R11:** use a `threading.Event` in the cleanup worker. Better still, trigger cleanup from the
  screenshot write path (it's the only producer) and keep a slow sweep as a backstop.

### R12–R14

Folded into Part 2 (organization) and Phase 5.

---

## Part 2 — New findings

### A. Organization and deduplication

**N-O1 — `_runtime_dir()` is copied 4 times, and the snippets directory is resolved 4 ways.**
`main.py:31`, `app/app_config.py:28`, `app/google_calendar.py:34`, and
`app/views/community_mod_view.py:24` each define `_runtime_dir()`. The snippets directory is
built separately in `factions_view._snippets_dir`, `target_types_view._snippets_dir`, and
`screen_capture._SNIPPETS_DIR`. Two of those are relative to `__file__`, one is relative to the
project root, and `ScreenCapture.snippets_dir` is a bare relative path that depends on the
current working directory.
→ Create a leaf module `app/paths.py` (no project imports, so it can't create an import cycle)
with `runtime_dir()`, `resource_dir()`, `snippets_dir()`, `screenshots_dir()`, and
`settings_path()`, and use it everywhere. In the frozen (PyInstaller onedir) build, snippets
currently resolve inside `_internal/`. That means user-captured templates and uploaded snippets
are **overwritten on every reinstall/upgrade**. Decide deliberately: bundled defaults stay in
`_internal`, and user additions go under `runtime_dir()`, with lookups checking user first,
then bundled.

**N-O2 — Duplicated Windows bootstrap code in `launcher.py` and `main.py`.**
`_is_admin`, `_relaunch_as_admin`, and `_acquire_single_instance_lock` exist in both
(`launcher.py:131-157`, `main.py:134-170`).
→ Move them to `app/win_process.py` (leaf module) and import from both.

**N-O3 — Eight hardcoded per-faction reputation routes nobody calls.**
`reputations_view.py` has `/`, `/augment`, `/rogue`, `/bajoran`, `/terran`, `/dti`,
`/section31`, and `/ex-borg`, each hardcoding a table name. That is a parallel copy of the
DB-driven registry. The frontend only uses `/all` and `/by-table/<name>`.
→ Delete them. `/by-table/<name>` already covers them using the allowlisted registry.

**N-O4 — Target preference values are defined in three places.**
`_ALLOWED_PREFERENCES` appears in `target_types_view.py:29` and `target_types_dao.py:303`, plus
the DB `CHECK` constraint.
→ Keep one constant in the DAO (exported without an underscore). The view and the Pydantic
`Literal` import it.

**N-O5 — Orchestrator boilerplate and string-sniffed status codes.**
Every orchestrator repeats `try: window = self.sc.get_and_activate_window() except
RuntimeError: return {"error": ...}`. `_run_capture` then picks 404 vs 500 by searching the
message text for `"not found"` (`capture_screen_view.py:33-45`). `identify_faction` duplicates
`_run_capture` inline.
→ Introduce `class GameWindowNotFound(RuntimeError)` and a small `BaseOrchestrator` with
`self.sc` and `_activate()`. Orchestrators raise instead of returning error dicts. `_run_capture`
maps exception types to status codes, and `identify_faction` uses `_run_capture`.
`process_event_rewards.py` is a placeholder. Confirm it raises `NotImplementedError` rather than
returning a fake success, and disable its button in the UI per the "no stub handlers" rule.

**N-O6 — Frontend: duplicated helpers and error handling.**
- `formatCargo`, `formatIntercept`, and `handleAttack` are copy-pasted between
  `Combat.jsx:26-35,156` and `SystemTargets.jsx:15-24,153`, and the candidate table is very
  likely duplicated as well. `targetFlags.jsx` already set the precedent for sharing between
  these two pages. Extend it to a `components/TargetCandidates/` folder (table + formatters +
  `useAttackTarget` hook), following the component-colocation convention.
- The string `'Cannot reach the server. Is the backend running?'` and the
  `if (!error.response) alert(...)` pattern appear about 15 times. Add a shared
  `frontend/src/api/client.js` axios instance (base URL, timeouts), plus an
  `errorMessage(err)` helper. Swap `alert()` for an inline status/toast component over time;
  review finding "catch blocks only log to console" belongs here.
- **Build-breaking on a fresh clone:** `ContextMenu/` and `HostileTemplateCapture/index.js` are **untracked**, but tracked files import them (`Dashboard.jsx:25`, `Combat.jsx:13`).
  Commit them before anything else.

**N-O7 — Dead code to remove.**
Unused DAO methods: `FactionSelectedSnippetsDAO.get_all_snippets`, `.set_snippets_for_faction`,
`FactionsDAO.get_faction_names`, `StatusEntriesDAO.get_all_entries_for_factions_summaries`
(which also has a misleading comment), `Database.get_factions_dao`, and
`ReputationsDAO._resolve_name_col`, which always returns `"name"` but is threaded through six
call sites. `system_view.py` duplicates the `/swagger` redirect that `main.py` already provides.
`check_events_exist` and `check_territory_systems` in `google_calendar.py` share about 60
near-identical lines. Fold them into one `_find_events(service, [(name, day_start)])` helper.
`find_next_reputation_name` and `find_next_reputation_low_limit` run the same query. Merge them
into one method returning `(name, low_limit)`.

**N-O8 — `settings.yaml.example` has drifted.** It is missing the entire `combat:` section and
several `templates:` keys. Add a test that asserts every key path in `settings.yaml` exists in
the example (values may differ).

### B. User-facing speed

These are ordered by likely payoff.

**N-P1 — Every DB call opens a new TCP+TLS connection to Neon.**
`Database.connect()` calls `psycopg2.connect()` each time (`database.py:46`). With a remote
Neon host, that handshake typically costs much more than the query itself.
→ Use `psycopg2.pool.ThreadedConnectionPool(minconn=1, maxconn=8)` inside `Database.connect()`.
The context-manager API stays the same, so no DAO changes. On the Neon pooler endpoint this is
safe as long as no session-level state is relied on. The advisory lock in `init_database` should
keep using a dedicated non-pooled connection (`DATABASE_URL_DIRECT`), which also matches Neon's
guidance for session locks.

**N-P2 — `/api/factions/summary` is an N+1 query.**
Per faction: a recent-entries query, a `COUNT(*)`, then up to 3 reputation queries
(`factions_dao.py:241-383`). That's roughly 5 × (number of factions) round-trips on the
Dashboard's main call.
→ Make it one SQL statement: `ROW_NUMBER() OVER (PARTITION BY faction_code ORDER BY timestamp
DESC)` for the last N entries, plus `COUNT(*) OVER (PARTITION BY faction_code)`. Reputation tiers
are static seed data, so load each DAO's tiers into memory once at startup (and refresh after
the reputation-row PUT). Then rep level, next level, and goal value are pure Python lookups.
Result: 1 query instead of about 40.

**N-P3 — The Dashboard downloads the entire history twice on load.**
`useEffect(..., [])` calls `loadFactions().then(loadEntries)`. `loadFactions` then sets
`factionColorsMap`, which triggers a second effect (`Dashboard.jsx:190-194`) that calls
`loadEntries` again. The second call only exists because `updateChart` reads a stale
`factionColorsMap` from its closure. `/api/status_entries/all` returns *every row ever*, and the
table keeps growing.
→ Build the color map from the `factionList` argument inside `loadEntries` and delete the
second effect. Add a `since` (or `days`) query parameter and default the chart to e.g. 30 days,
with a "show all" toggle. Fetch the calendar status in parallel (`Promise.all`) instead of
treating it as independent.

**N-P4 — Startup does slow work in the wrong order.**
`app = create_app()` runs at import time (`main.py:310`), which does the full schema init over
the network. Then the cert is generated and the HTTPS thread started (`main.py:327-333`).
*Only then* does the code check admin rights and maybe relaunch (`main.py:335-337`), throwing
all of that away. The EasyOCR model loads lazily on the first capture, so the first click
appears to hang for several seconds.
→ Order it as: single-instance lock → elevation check → env/config validation → `create_app()`
(with the R7 version check that skips work at head) → listeners. After startup, warm
`get_reader()` on a background thread so the first capture is fast. Also check whether the
mutex release on relaunch can race the elevated child. Today the child's heavy imports make it
lose the race harmlessly, but passing the handle or waiting on parent exit would make that
deterministic.

**N-P5 — Territory list waits on Google Calendar, one API call per system.**
`GET /api/territory/systems`, the `POST`, and the `PUT` all call `check_territory_systems`
synchronously, and that function makes one `events.list` call per system
(`google_calendar.py:168-245`). Saving a single row triggers a calendar round-trip before the
UI updates.
→ Return DB data immediately and let the frontend call `POST /systems/check-calendar` as a
second, non-blocking request. Inside the check, make **one** `events.list` call covering the
next 7 days and match system names in memory.

**N-P6 — Capture-path micro-costs.**
`capture_mode` defaults to `"disk"`: each poll writes a PNG and re-reads it. `capture_window`
filenames have one-second resolution (`screen_capture.py:643`), so captures in the same second
overwrite each other. `_get_columns` hits `information_schema` on every `get_all` / `get_last`.
→ Default to `memory` + `write_behind: true` (keeps debug PNGs without blocking), use `%f` in
disk-mode filenames as memory mode already does, and cache the column lists with the tier cache
from N-P2.

### C. Stability

**N-S1 — Nothing stops two automations from driving the mouse at once.**
Every capture route is synchronous and unguarded. A double-click, the Combat page's 4-second
refresh loop running while the user hits "Gifts" on the Dashboard, or two open tabs will have
two threads clicking the game at the same time.
→ Add a process-wide `automation_lock = threading.Lock()`. `_run_capture` does a non-blocking
acquire and returns **409 `{"error": "Another capture is in progress"}`** on contention. The
frontend disables capture buttons while any capture is running (one shared `isCapturing` state
via the API client).

**N-S2 — `settings.yaml` writes are non-atomic and race-prone.**
`_add_combat_template` (`app_config.py:74-118`) reads, edits, and rewrites the file in place
with no lock. A crash mid-write leaves a truncated `settings.yaml`, and the app then silently
falls back to defaults because `_load` catches everything. It also matches the first `key:`
anywhere in the file, not just under `combat:`.
→ Hold a lock, write to `settings.yaml.tmp`, then `os.replace()`. Scope the key search to the
`combat:` block. Narrow `_load`'s `except Exception` to `(OSError, yaml.YAMLError)` and make a
parse failure **fatal at startup** rather than silently running with default thresholds.

**N-S3 — Wrong status codes caused by broad `ValueError` mapping.**
- `status_entries_view.py:108-111`: `int(value)` runs inside the try, so `{"value": "abc"}`
  returns **404** with Python's `invalid literal for int()` text.
- `factions_view.py:260`: a duplicate name/code on update (a `UniqueViolation` turned into a
  `ValueError`) returns **404** instead of 409.
- `factions_view.py:177`: the same `int(...)` problem on create returns 400 with internal
  text.
→ R4's Pydantic parsing removes the conversion errors. Add `NotFoundError` / `ConflictError`
domain exceptions in the DAO layer so routes map types, not messages.

**N-S4 — Snippet upload/delete leaves the filesystem and DB out of sync.**
The upload saves the file *before* the DB insert and only cleans up on `ForeignKeyViolation`
(`factions_view.py:66-78`). Any other DB error leaves an orphaned file, and a check-then-write
race exists on `os.path.exists`. Delete removes the row but keeps the file (by design, per the
UI text), so orphans accumulate.
→ Open with `"xb"` (exclusive create) instead of exists-then-save. Wrap the insert so *any*
failure removes the file. Validate content with `cv2.imdecode` (also covers the review's
"content verification" note), and cap upload size via `MAX_CONTENT_LENGTH`. Optionally add a
"delete file too" checkbox.

**N-S5 — Status-entry timestamps are `TEXT`.**
Ordering and the rate math in `_compute_faction_status` depend on every row having the same
ISO-8601 format and offset. One differently formatted row (manual SQL, an older code path)
silently mis-sorts.
→ As a versioned migration (R7): `ALTER COLUMN timestamp TYPE timestamptz USING
timestamp::timestamptz`, plus an index on `(faction_code, timestamp DESC)`. That index also
makes N-P2's window query cheap. Also drop or populate the unused `value_delta` column, which
CLAUDE.md already documents as "exists but not populated".

**N-S6 — Errors swallowed silently.**
`territory_view._annotate_with_calendar` uses `except Exception: pass`. `is_authenticated` does
the same. `reputations_dao.get_all` wraps *every* exception into a `ValueError` carrying the raw
DB message. `ScreenCapture.__init__` and `get_stfc_window` catch `Exception`.
→ Log at warning level with context, narrow to the expected types (`GoogleAuthError`,
`OSError`, `psycopg2.Error`), and stop wrapping DB errors into `ValueError`, which routes treat
as user-safe 4xx text. Also fix the stale docstring on `google_calendar._build_service`. It says
the OAuth flow "is run automatically". The code correctly raises instead, which is the required
behaviour.

### D. Safety (beyond R2)

**N-X1 — Exception text returned to clients.** `capture_and_identify_faction` returns
`{"error": str(e)}` for *any* exception (`process_reputations.py:201,213`), and the error-dict
convention in orchestrators passes raw messages through `_run_capture`. N-O5 fixes the
structure. Until then, make sure only curated messages go into `{"error": ...}`.

**N-X2 — `send_from_directory` on `<path:filename>`.** `get_snippet_image` and
`get_sample_image` are safe against traversal (Werkzeug's `safe_join`), but they serve
**any** file in the snippets directory, including the 2.9 MB `favicon.zip`. Restrict them to
image extensions.

**N-X3 — Docker Compose ships `SECRET_KEY: change-me-in-production` and a fixed DB password.**
With R1 fixed, reject known placeholder values in the production settings validator so the
default can't be deployed by accident.

### E. Found while building the Phase 1 tests (2026-11-06)

**N-T1 — DDL drifted from the live schema (fixed in 8145ca2).** The `CREATE TABLE` statements
declared reputation limits and `status_entries.value` as `INTEGER`. The live database had
already been widened to `BIGINT`, so only fresh installs broke: FKR seeding failed with
"integer out of range". The DDL now matches. **Still drifted:** the code declares
`status_entries.value_delta`, but the live table doesn't have it. Live `id` columns are
`BIGINT`, while the code uses `SERIAL`. Fold both into R7 (versioned migrations), so the code
becomes the source of truth again.

**N-T2 — `parse_time_remaining` turns ordinary words into minutes.** The lookalike map reads
the "i" in "time" as "1", so `"no time here"` parses as one minute. Callers currently filter
with `is_time_string()` first, so users don't see it. Fix this when real OCR crops are
checked in as fixtures. It's recorded as a strict xfail in `tests/test_ocr_text.py`.

**N-T3 — `settings.yaml` is read and written without `encoding="utf-8"`.** On Windows that
means cp1252, and the file contains non-ASCII characters such as "×". Fix this together with
N-S2 (atomic settings write).

**N-T4 — `uv lock` is broken.** `.python-version` pins 3.13, but `requires-python` is
`>=3.14`. Pick one. Until then, dev dependencies live in `requirements-dev.txt`.
- **Done 2026-11-07** (`evan-python-315`, a branch name kept from an abandoned first try): the project is on
  **Python 3.14** in `.python-version`, `requires-python` and the Docker base image. `uv lock` resolves and
  `uv sync --frozen` installs on 3.14.7 with no source builds. The suite passes (286 passed and 1 strict xfail), and
  easyocr, torch, cv2, skimage and pywin32 all import.
  - `python-dotenv` was pinned to 1.1.0, but `pydantic-settings` 2.16.2 needs `>=1.2.2`. It's now 1.2.4, the version
    the venv already ran.
  - The lock's unpinned dependencies were refreshed (`uv lock --upgrade`), for example torch 2.15. `psycopg2-binary`
    is 2.9.13, and `requirements-docker.txt` matches the lock (`rpds-py` 2026.9.1, `MarkupSafe` 3.0.4).
  - `requirements.txt` had drifted from the lock (torch 2.13 against 2.15, among others). It is now generated by
    `uv export`, so the lock is the one source.
  - **3.15 was tried first and dropped.** `scikit-image` has no 3.15 Windows wheel before 0.27.0rc1 (0.26.0 won't
    compile), and `pyyaml` / `pyclipper` only build from source. Revisit once those ship 3.15 wheels.
  - **Installer moved 2026-11-07:** the Inno installer bundles embedded Python 3.14.7 (it was 3.12.9). Its torch pin
    was hardcoded (`torch==2.10.0+cpu`); `prepare.bat` now writes `requirements_torch.txt` from `requirements.txt`, so
    it follows the lock (2.15.0 / torchvision 0.29.2, both with Windows CPU wheels). Not yet built or installed
    (see below).
  - **PyInstaller build moved 2026-11-08/09:** PyInstaller wasn't in any manifest, so the 3.14 venv didn't have it.
    It's now a pinned dev dependency (6.22.3). The spec's hardcoded psycopg2 DLL list named hashed files from an
    older psycopg2 and broke the build; PyInstaller's psycopg2 hook collects `psycopg2_binary.libs` on its own
    (`be1e2bc`). Rebuilt 2026-11-09 with a fresh frontend build. `dist/STFCRepTracker` bundles `python314.dll`,
    and the bundle is 835 MB (the 3.13 build was 1.1 GB). The build passes, but the exe hasn't been started.
    - The first rebuild failed: PyInstaller couldn't delete the old `dist` folder because some directories were
      flagged read-only, which Windows refuses to delete. The build copied the flag from `app/screen_snippets`,
      `app/screen_snippets/Attic` and `frontend/dist`, which have since been cleared with `attrib -R`. Git doesn't
      track that flag, so a fresh clone is unaffected, but it can come back locally. If a rebuild fails with
      `PermissionError` while removing `dist`, run `attrib -R dist\STFCRepTracker\* /S /D` and build again.
    - **Still open:** build and run the Inno installer on 3.14, then do the Phase 5 snippet-across-reinstall check.

**N-T5 — Test coverage gaps, deferred.**
- `_extract_points` (needs EasyOCR and checked-in screen crops).
- Snippet upload (writes into the real snippets directory, so it needs a configurable path
  first).
- A `windows` marker for UI-automation smoke tests.
- Extracting `create_app()` out of `main.py`, so tests stop importing the entry point.

### F. Found in the browser checks (2026-11-07)

The checks ran against a scratch schema on the Neon test branch, filled with that branch's copy of production
(11 factions, 750 entries, 24 snippets), with `DISABLE_CAPTURE=1`. The live database was not touched.

**N-B1 — Calendar sign-in timed out after 30 s (Phase 5 regression, fixed).** The shared client
(`07f2095`) gave every request a 30 s ceiling. `POST /api/calendar/auth` answers only after the user finishes
Google's consent page, so the modal reported "auth failed" while the server kept waiting. It now gets
`INTERACTIVE_AUTH_TIMEOUT_MS` (5 min). It's the only non-capture call that waits on a person. The build passes;
the real consent flow wasn't re-run.

The rest predate the refactors:

**N-B2 — One reading shows "Unknown".** `_compute_faction_status` returns before the tier lookup when a faction
has fewer than 2 entries. The `time_diff_mins <= 0` branch returns the right `rep_level` but leaves
`status.reputation_level` as "Unknown". A new faction with one value of 150,000 (Rogue tiers) showed "Unknown";
after a second value it showed Accomplice.
- **Fixed 2026-11-07:** the tier, next tier and goal come from the newest value whenever there is one. Rates
  and time to goal still need two entries a positive time apart. Two contract tests (one entry, two entries at
  the same timestamp) fail without the fix. Suite: 288 passed and 1 strict xfail (N-T2).
- Not changed: with no rate yet, the card shows the next tier with an ETA of "0", as it already did for a
  stalled faction.

**N-B3 — Augment tiers stop at 1,000,500.** Augment at 13.9m shows "Unknown". The seed and production agree,
so the tiers above "Ally, Capped" are missing data.
*Decision 2026-11-07:* when a table has no next tier, the faction is capped at the table's top tier, including a
value past the top tier's `high_limit`. The summary sends `status.capped = true` with no goal and `minutes_to_goal`
null, and the card shows "Capped at <tier>" with a full progress bar. Augment at 13.9m now reads "Ally, Capped".
*Fixed 2026-11-07.*

**N-B4 — `on_chart` doesn't hide anything.** It only seeds empty factions into the chart legend; every faction
with data is charted. Ten factions have `on_chart = 0` and are charted anyway. Decide what it should mean.
*Decision and fix 2026-11-07:* `on_chart` sets whether a faction's series is **shown when the chart loads**. Every
faction is in the legend, and series with On Chart off (or nothing to draw) start hidden, one click away. Legend
choices are now kept by faction name and survive reloads after a capture or quick entry; before, they were keyed by
position and reset on every reload. The Factions form reads "Shown at load" / "Hidden at load".

**N-B5 — Opening TC Schedule starts the OAuth flow.** If the token is missing, opening the modal POSTs
`/api/calendar/auth`, which opens Google's consent page. It is the dedicated auth endpoint, but nobody clicked
"connect". An explicit button would match the auth rule in `CLAUDE.md`.
*Fixed 2026-11-07:* opening the modal only loads the schedule and, when a token exists, checks the calendar. Without
one it shows "Not connected" with a **Connect Google Calendar** button, and only that click POSTs
`/api/calendar/auth`. The backend already kept OAuth out of the data endpoints; two comments in
`google_calendar.py` that said otherwise were corrected.

---

## Part 3 — Phased roadmap

Each phase is independently shippable, and each phase's verification gate must pass before the
next one starts.

### Phase 0 — Hygiene (≈1 hour, no behaviour change)
- Commit the untracked `ContextMenu/` and `HostileTemplateCapture/index.js` (N-O6).
- Add `.gitattributes`, then renormalize line endings in a separate commit (R9).
- Fix the port in `AGENTS.md` / `CLAUDE.md` (R8). Fix the `logging.yaml` names and format (R10).
- Sync `settings.yaml.example` (N-O8).
- **Verify:** `npm run build`; the app starts; log lines show `file:line`.

### Phase 1 — Test harness (prerequisite for everything below)
- Add pytest, `tests/conftest.py` with a disposable Postgres, and the contract and pure-function
  tests listed in R6. Add `TESTING_STANDARDS.md` to `CLAUDE.md`.
- **Verify:** `pytest` passes against a throwaway DB, and the suite fails if you revert one
  known fix (e.g. N-S3's 404).
- **Done 2026-11-06** (`evan-phase1-tests`): 75 passed and 5 strict xfails against a Neon test
  branch. Reverting the BIGINT DDL fix or either `current_schema()` fix fails the suite. The
  xfails stand for R2, N-S3 (×3) and N-T2, and each one flips to a failure when its fix lands.
  New findings are listed under Part 2 E.

### Phase 2 — Safety and correctness quick wins
- R2 steps 1–3 (Origin-check CSRF guard, drop `force=True`, 7443 to loopback), R1 (pydantic-settings),
  R3 (JSONL + lock + `MAX_CONTENT_LENGTH`), N-S1 (automation lock → 409), N-S2 (atomic settings
  write), N-S3 / R4 (Pydantic request models + domain exceptions), N-X2, N-X3.
- **Verify:** new tests for each item, plus a manual check that a cross-origin `text/plain`
  POST to `/api/status_entries/` is rejected and the UI still works unchanged.
- **Code done 2026-11-06** (`evan-phase2-safety`): 166 passed and 1 strict xfail (N-T2). The R2 and N-S3
  xfails now pass, and each new guard was checked by reverting it and watching its test fail.
  **Manual check done 2026-11-07:** a `text/plain` POST from another origin (`127.0.0.1:8765`) got a 403 and was
  logged, with no row written. A same-origin save from the Dashboard still returned 201. See Part 2 F.
- Deviations from the plan, each for a reason found during the work:
  - **R2:** the 7443 app has **no** CORS at all. All 214 captured mod requests carry no `Origin`, so nothing
    needs to read responses cross-origin.
  - **R3:** the community cap is **per request**, not an app-wide `MAX_CONTENT_LENGTH` on the main app,
    which would also cap snippet uploads. Werkzeug truncates a chunked body at the limit instead of
    rejecting it, so the route reads limit+1 bytes and rejects on the extra byte. The old
    `community-data.json` is left untouched; new captures go to `community-data.jsonl`.
  - **R4:** routes no longer catch `Exception`. One app-level handler logs the traceback and returns a
    generic 500. `TargetPreference` (N-O4) and `TemplateKind` became single sources along the way.
  - **N-S2:** the writer also re-reads the list from disk under the lock, so hand edits made while the app
    runs are kept. It refuses any edit that would change more than that one list.
  - **N-X3:** compose requires `SECRET_KEY` (`${SECRET_KEY:?…}`). The internal DB password stays fixed,
    since the db service isn't published.
- Deferred, for Phase 5 (Part 2 A):
  - the cwd-relative `ScreenCapture.snippets_dir` and the `_runtime_dir()` copies
  - the raw SQL in `reputations_view`
  - N-S6's `ValueError` wrapping in `reputations_dao.get_all`

### Phase 3 — Speed
- N-P1 (connection pool), N-P2 (single-query summary + in-memory tier cache), N-P3 (single
  history fetch + `since` window), N-P5 (async calendar annotation, one API call), N-P4 (startup
  order + OCR warm-up), N-P6 (capture-mode defaults, cached columns).
- **Verify:** time `/api/factions/summary` and Dashboard first paint before and after (browser
  devtools). Expect the summary to drop from ~40 round-trips to 1, and the Dashboard to make
  half as many history requests with a far smaller payload.
- **Code done 2026-11-06** (`evan-phase3-speed`): 200 passed and 1 strict xfail (N-T2). Each new guard
  (pool discard, idle ping, wait-not-fail, cache refresh after a tier PUT, per-faction average window) was
  checked by breaking it and watching its test fail.
  - `get_faction_summary()` with 8 factions × 200 entries on the Neon test branch went from 1,668 ms to 93 ms
    median. Over HTTP on a real startup it took 122 ms. The test suite went from 91 s to 58 s, almost all of it
    from connection reuse.
  - **Browser check done 2026-11-07:** the Dashboard makes 2 API calls on load: `/api/factions/summary` in 194 ms
    (8.2 KB) and `/api/status_entries/all?days=30` in 107 ms (7.6 KB). "Show all history" works. First paint
    takes about 1.1 s. Most of it is the lazy Dashboard chunks (~780 ms) from Flask's debug server, not the API.
- Deviations from the plan, each for a reason found during the work:
  - **N-P1:** `ThreadedConnectionPool` raises once it's exhausted, so a semaphore makes callers wait. Neon drops
    idle connections on suspend, so a connection idle for more than 30 s gets a `SELECT 1` before reuse.
    `DATABASE_URL_DIRECT` was required but never read until now; it now carries the init advisory lock.
  - **N-P2:** making the cache correct meant moving the reputation-row PUT into `ReputationsDAO.update_row`.
    That was a Phase 2 deferral (the raw SQL in `reputations_view`), done early. The same rewrite removed
    `get_last` and `_resolve_name_col` (part of N-O7) and N-S6's `ValueError` wrapping in `get_all`.
    A faction whose DAO isn't registered now falls back to any DAO already serving its table, instead of
    building one with a connection passed in as `db`.
  - **N-P3:** the window is `days=N` (not `since`). The query string is now validated (`StatusEntriesQuery`,
    `parse_query`), so bad `limit`/`offset` are 400 instead of silently returning the whole table.
  - **N-P4:** importing `main` builds nothing any more. Gunicorn uses `main:create_wsgi_app()`. The relaunch
    race is fixed by releasing the mutex before `ShellExecuteW`. The R7 "skip at head" check waits for Phase 4.
  - **N-P5:** `check_events_exist` (territory capture) had the same per-system loop, so both functions now share
    one single-call implementation. Matching is a case-insensitive title substring, while Google's `q` also
    searched descriptions and locations.
  - **N-P6:** code defaults and `settings.yaml.example` now say `memory` + `write_behind: true`. The tracked
    `settings.yaml` still says `write_behind: false`, which is left as the owner's choice.
- Found along the way: `uv lock` fails before resolving anything (`.python-version` 3.13 vs `requires-python >=3.14`,
  and `python-dotenv==1.1.0` vs a dependency that needs `>=1.2.2`), so `uv.lock` was not refreshed for the new
  direct `httplib2` entry.

### Phase 4 — Schema and lifecycle
- R7 lightweight versioned migrations; N-S5 `timestamptz` + index; R5 DAO-type endpoint,
  validation, and live registry update.
- **Verify:** migration test from an empty DB **and** from a copy of the current production
  schema (Neon branch). Creating a faction in the UI works without a restart.
- **Code done 2026-11-06** (`evan-phase4-schema`): 218 passed and 1 strict xfail (N-T2).
  - The whole suite now runs on a schema built only by migrations.
  - `test_production_copy_migrates_in_place` migrates the test branch's copy of production inside a transaction,
    checks it, and rolls it back.
  - Breaking the FK reconcile, the unique-name index, or the seed fingerprint check each fails a test.
  - Init at head takes 447 ms, against 2,301 ms on every start before (most of what's left is the TLS handshake).
    The first start on an empty DB takes 5.7 s.
  - **UI check done 2026-11-07:** the type picker lists all 8 implementations. A faction created with the Rogue
    type showed up at once, and with two values it read Accomplice → Known Associate, with no restart. One value
    alone shows "Unknown" (N-B2, older than this phase).
- Found by diffing the production copy against a fresh schema. Migration v2 fixes these:
  - `status_entries` / `faction_selected_snippets` FKs had no `ON UPDATE CASCADE` (one was `NOT VALID`), so renaming
    a faction code failed in production while the test passed on a fresh schema.
  - `factions.name` had no UNIQUE constraint, so the 409 path couldn't fire.
  - `reputation_dao_name` was `NOT NULL DEFAULT '"FKRReputationsDAO"'` (quotes included).
  - `value_delta` didn't exist in production, so `GET /api/status_entries/<faction>`, which selected it, failed there.
    It is dropped everywhere now.
  - An empty database got **no** tier tables until a faction referenced one and the app restarted.
- Deviations from the plan, each for a reason found during the work:
  - **R7:** tier tables aren't migrations. Each `*_reputations_dao.py` is seeded when a fingerprint of its seed rows
    changes (`reputation_seed`). Tier edits made in the UI now survive restarts; before, every start overwrote them.
    The DAOs lost their `create_table` methods: migration SQL is frozen in `migrations.py`, and a test checks the
    frozen `target_types` CHECK against `TargetPreference`. The startup snippet backfill moved to write time
    (`default_unselected_snippet`). A database newer than the code refuses to start.
  - **R5:** instead of registering and unregistering DAOs per faction, every implementation is registered at startup,
    keyed by table. Factions resolve their DAO by table name, so create, rename and type changes need no registry
    bookkeeping. `reputation_dao_name` is filled in from the table and must match it when sent. The base-class
    `ReputationsDAO(db, table)` path is gone, since no faction used it.
  - **N-S5:** the API still returns ISO-8601 UTC strings (`iso_utc`). Removed the dead
    `get_all_entries_for_factions_summaries` (N-O7) rather than port it.

### Phase 5 — Structural refactors (incremental, behind tests)
- N-O1 `app/paths.py` (decide the user-vs-bundled snippets split first); N-O2
  `app/win_process.py`; N-O3, N-O4, and N-O7 dead and duplicate code; N-O5
  `BaseOrchestrator` + typed exceptions.
- Frontend: shared API client (if not done in Phase 2), `TargetCandidates` component, then split
  `Dashboard.jsx` (~1,000 lines) into `FactionCards`, `HistoryChart`, `CaptureToolbar`, and
  `TerritoryScheduleModal` folders, each with its own hook.
- OCR modules (R12): pull pure parsing/scoring out of `process_system_targets.py` and
  `process_territory_capture.py` into `*_parsing.py` modules covered by the Phase 1 fixtures,
  leaving orchestration in place. Add type hints as each module is touched (R13).
- R14: remove `favicon.zip`, the root `package-lock.json`, root `Territory.jpg`, and the
  `2026-09-14_*.jpg` screenshot after confirming nothing references them. Move any image that a
  test needs into `tests/fixtures/`. Optimize the 2.2 MB `favicon.svg`.
- **Backend half done 2026-11-06** (`evan-phase5-refactors`): 235 passed and 1 strict xfail (N-T2).
  - **N-O1:** `app/paths.py` (leaf) has `runtime_dir` / `resource_dir`, and `app/snippet_store.py` handles snippets.
    The split decision: lookups check the user folder (under `runtime_dir`) first, then the bundled one (`_internal`).
    Every new snippet goes to the user folder. In a source checkout both are the same folder. Screenshots now follow
    the `screenshots_dir` setting everywhere, instead of the process cwd.
  - **N-O2:** `app/win_process.py` holds `is_admin`, `relaunch_as_admin`, and `SingleInstanceLock`.
  - **N-O3 / N-O7:** the 8 per-faction routes, `system_view.py`, 3 unused DAO methods, and the whole unused
    `app/models/` package are gone. The rest of N-O7 landed in Phases 3–4.
  - **N-O5:** `capture_errors.py` + `BaseOrchestrator`. `_run_capture` maps types to status codes, and each message
    keeps its old status. Exceptions: `save_template`'s request errors are now the documented 400s, and Event
    Rewards is a 501 with its button disabled. This also closes N-X1.
  - **R14:** done, except `Territory.jpg`, which stays until R12 decides whether it becomes a parser fixture.
    `favicon.svg` went from 2.2 MB to 134 KB.
  - Breaking the user-first snippet lookup, or the type→status mapping, fails a test.
  - **Frontend done the same day:** `src/api/client.js` (the only axios importer, with timeouts and
    `errorMessage`) and `components/TargetCandidates/`. `Dashboard.jsx` went from about 1,050 lines to 70 and is split
    into `FactionCards`, `HistoryChart`, `CaptureToolbar` and `TerritoryScheduleModal`, each with its own hook, one
    commit each, with a build after each.
    - Removed the unreachable "Territory Capture Calendar" results. Its button was removed in `cb43582`.
    - Every converted call site uses `errorMessage`, and several silent failures now say so.
    - **Browser check done 2026-11-07:** each Dashboard section, Combat and System Targets render. Failed
      requests show their message, and the Combat loop stops on a failed scan. Found one regression, N-B1
      (calendar auth timeout), fixed the same day.
  - **R12/R13 done the same day:** `territory_parsing.py` and `system_targets_parsing.py` hold the pure logic. Their
    tunables come in as arguments, not from settings. Template matching, OCR and clicks stay in the `process_*.py`
    files. The extraction also removed duplicates: the territory row dict (3 copies), the confidence filter (3, now
    `ocr_text.confident_tokens`), the approved-type and reachability loops (2 each), and the empty-measurements
    dict (4).
    - `Territory.jpg` became `tests/fixtures/territory_page.jpg`, which closes R14.
    - `test_territory_fixture.py` runs real template matching on that fixture, without OCR. Lengthening the strip
      formula fails it.
    - Suite: 278 passed and 1 strict xfail (N-T2).
    - **Not covered:** the OCR reads themselves (N-T5: needs EasyOCR in the suite) and N-T2's parser bug, which still
      waits for real OCR crops as fixtures.
  - **Manual check still open:** a frozen build should keep an uploaded snippet across a reinstall.
  - **R11 done the same day:** `app/screenshot_retention.py` replaces main's 5-minute polling loop. Both screenshot
    writers (`capture_window` and the write-behind worker) call `notify_written()`, which only sets an Event. The
    pruner thread wakes on it, keeps the newest 30 files, and sweeps every 30 minutes as a backstop. `stop()` ends it.
    - Found along the way: `_save_debug_crop` built its folder from `__file__`, ignoring the `screenshots_dir`
      setting, and its second-resolution names overwrote each other. It now uses `screenshots_dir()/debug` with
      microsecond names. The pruner leaves subfolders alone, as before.
    - Turning the signal into a no-op fails 3 tests. Suite: 286 passed and 1 strict xfail (N-T2).

### Deliberately not recommended
- **A full auth system.** It's only worth building if LAN or remote access becomes a goal.
  R2's CSRF guard plus loopback binding covers the actual threat.
- **Alembic now.** The lightweight version table covers current needs (R7).
- **Background job queue / SSE for captures.** The automation lock plus synchronous requests is
  enough for one user. Revisit if captures need progress reporting.
- **A big-bang Dashboard rewrite.** Extract one section per change behind the build check.
