# STFC Rep Tracker — Full Project Review

**Review date:** 2026-11-03  
**Scope:** Flask API, PostgreSQL data layer, Windows/OCR automation, React SPA, configuration, packaging, Docker, documentation, and repository hygiene.  
**Method:** Manual source review, standards comparison, targeted searches, Python bytecode compilation, and a Vite production build. No live PostgreSQL, Google Calendar, STFC client, OCR workflow, installer, or Docker runtime was available, so those boundaries were reviewed statically rather than exercised end to end.

## Executive summary

The project has a coherent single-user architecture and several good recent improvements: database connections generally use a safe context manager, dynamic reputation DAOs are allowlisted before dynamic SQL is used, API errors are often sanitized, frontend writes use Axios (which rejects non-2xx responses), and Windows-only capture imports are excluded from the container path. The frontend builds and the Python source compiles.

The largest risks are at deployment boundaries. Production Flask configuration currently sets `SECRET_KEY` to a Python `property` object instead of the configured string. The application also exposes unauthenticated write and game-control endpoints on non-loopback interfaces in Docker and on the community-mod HTTPS listener. Request validation is mostly ad hoc rather than schema-based, and the community payload/file-writing path has size-limit and multi-worker concurrency weaknesses.

**Overall assessment:** functional but not production-hardened. Address the two critical findings before treating any non-loopback deployment as safe. The high-priority correctness and validation findings should follow before adding features.

## Findings

### Critical — production `SECRET_KEY` is not the environment value

**Evidence:** `config.py:32-41` declares `ProductionConfig.SECRET_KEY` as an instance `@property`, while `main.py:272` passes the class returned by `get_config()` to `Flask.config.from_object`. Accessing the attribute on that class yields the descriptor itself. A direct check returned `property <property object ...>` even with `SECRET_KEY=abc`.

**Impact:** Flask receives a shared, non-string descriptor rather than the deployment secret. Anything relying on signed sessions, flash messages, CSRF integrations, or other Flask signing can fail or behave insecurely. The intended “fail if absent in production” check also never runs.

**Recommendation:** validate environment configuration before constructing the app and assign a real string value. Prefer a typed settings model (Pydantic Settings per project standards), or make `get_config()` return an initialized configuration mapping/object whose `SECRET_KEY` has already been validated. Add a startup test that loads production configuration and asserts the exact configured string.

### Critical — unauthenticated mutation and automation endpoints are network-accessible

**Evidence:** the API has no authentication or authorization layer. It contains endpoints that mutate data, upload files, create Google Calendar events, write settings, and trigger screen automation/attacks (for example `app/views/factions_view.py:42-80`, `app/views/territory_view.py:98-125`, and `app/views/capture_screen_view.py:47-449`). Docker publishes `7300:7300` and Gunicorn binds `0.0.0.0:7300`. The community-mod listener explicitly binds `0.0.0.0` at `main.py:239` and enables unrestricted CORS at `main.py:233`.

**Impact:** another device on the LAN—or browser-delivered requests in some threat models—can change tracker data, write files, create calendar events, and, on the Windows listener, initiate actions against the running game. CORS is not an access-control mechanism and does not prevent requests from being sent.

**Recommendation:** default every listener to loopback. If remote access is intentional, place authentication and authorization in front of all API routes, require an explicit opt-in bind address, restrict CORS to configured origins on both Flask apps, and add CSRF protection where cookie-based authentication is used. Treat attack/capture and file-write routes as privileged operations. In Docker, publish to `127.0.0.1:7300:7300` by default.

### High — community payload limit can be bypassed and concurrent appends can corrupt the capture file

**Evidence:** `app/views/community_mod_view.py:64-76` rejects only when `Content-Length` is present and too large, then parses the full body. Chunked or missing-length requests bypass this check. `main.py:232-241` creates a separate Flask server without `MAX_CONTENT_LENGTH`. `app/views/community_mod_view.py:93-97` appends a multi-write JSON document to one file without a lock. The same blueprint is also registered on the main app (`main.py:283`), and Docker runs two Gunicorn workers, allowing interleaved writes.

**Impact:** an oversized request can consume excessive memory/disk, and simultaneous requests can produce malformed, interleaved records. The output format is also not valid JSON as a whole, complicating reliable recovery.

**Recommendation:** configure Flask’s `MAX_CONTENT_LENGTH` on both apps and retain an application-level size check for clear errors. Serialize writes with a process-safe lock or, preferably, store each event transactionally in PostgreSQL or as one atomic file per event. If a stream file is retained, use JSON Lines with one atomic serialized line per record.

### High — external request bodies are not validated with schemas

**Evidence:** routes repeatedly use `request.get_json(... )` plus manual `.get()`, `int()`, and `float()` conversion, including `app/views/factions_view.py:147-174`, `app/views/status_entries_view.py:98-108`, `app/views/reputations_view.py:134-176`, `app/views/territory_view.py:43-53`, and `app/views/capture_screen_view.py:295-362`. Pydantic is not declared as a dependency.

**Impact:** unexpected booleans, oversized strings, malformed colors/table/DAO names, out-of-range coordinates, non-finite floats, and inconsistent error responses can cross the HTTP boundary. Some conversion failures become 500 responses; other values reach SQL or automation logic with unclear semantics.

**Recommendation:** define Pydantic models for each request shape and convert `ValidationError` to a sanitized 400 response. Add domain constraints (string lengths/patterns, finite numbers, positive crop dimensions, coordinate bounds, valid time format, allowed enum values). Keep dynamic DAO/table identifiers tied to authoritative database metadata rather than accepting arbitrary names.

### High — creating a faction does not complete the dynamic-DAO lifecycle

**Evidence:** `app/views/factions_view.py:104-180` inserts faction metadata, including `reputation_table_name` and `reputation_dao_name`. Dynamic DAO classes are loaded only during `Database.init_database()` through `ReputationsDAO.initialize_dao_instances` (`app/database/database.py:73-81`). The route neither verifies that the named module/class exists nor creates/initializes the related reputation table/DAO at runtime.

**Impact:** the UI can report a faction was created while reputation endpoints and OCR processing cannot use it until restart—and may still fail after restart if the supplied DAO name/module is invalid. This violates the project’s documented cross-resource creation requirement.

**Recommendation:** make faction creation an explicit service operation. Validate the requested DAO against loadable/approved implementations, create and seed the associated table in the same transaction, update the in-memory registry only after commit, or reject runtime creation and document that it requires a migration/restart. Add a real PostgreSQL integration test for the complete flow.

### High — there is no automated test suite or boundary verification

**Evidence:** no test files or test command are present. The project performs dynamic SQL/DAO loading, startup DDL/seeding, filesystem writes, OAuth/calendar calls, and Windows UI automation, all without automated contract coverage.

**Impact:** schema drift, route/payload mismatches, configuration regressions (including the production secret bug), and OCR parsing regressions can ship undetected. Compilation and frontend bundling do not exercise these contracts.

**Recommendation:** add a focused pytest suite despite the current project note saying no suite exists. Highest-value tests are: production config loading; PostgreSQL schema initialization and dynamic DAO discovery; faction/status/reputation CRUD through Flask’s test client against real Postgres; community payload limits and concurrent persistence; settings mutation; and pure OCR parsing/scoring functions using checked-in fixtures. Keep Windows UI-driving tests separate and opt-in.

### Medium — startup DDL is being used as a migration system

**Evidence:** `Database.__init__` immediately calls `init_database()` (`app/database/database.py:30-47`), which acquires an advisory lock and runs table creation and reputation initialization on every process start (`app/database/database.py:65-88`). There is no migration directory or schema-version mechanism.

**Impact:** application startup has schema-writing privileges and behavior; irreversible changes, backfills, and version compatibility cannot be reviewed or rolled back cleanly. Multiple application versions pointed at one database are especially risky.

**Recommendation:** introduce versioned migrations (Alembic or carefully ordered SQL migrations) and make normal startup read-only with respect to schema. Retain advisory locking in the migration runner if concurrent deployment is possible.

### Medium — repository configuration and documentation disagree about the backend port

**Evidence:** `AGENTS.md:32` says port 7000, while `main.py:339`, `launcher.py:30`, `frontend/vite.config.js`, Docker, and Compose use 7300.

**Impact:** contributors and automation following the project instructions connect to the wrong port. This is exactly the kind of duplicated runtime value that silently drifts.

**Recommendation:** update the project documentation to 7300 and derive proxy/deployment values from one documented environment setting where practical.

### Medium — Windows line-ending policy is not enforced

**Evidence:** the required `.gitattributes` file is absent. The Windows standard requires `* text=auto eol=crlf` and `core.autocrlf=true`.

**Impact:** contributors can introduce mixed or LF-only endings, causing noisy diffs and possible failures in Windows scripts/tooling.

**Recommendation:** add the required `.gitattributes`, verify Git configuration, and normalize in a dedicated commit after reviewing the expected diff.

### Medium — logging configuration contains stale logger names

**Evidence:** `logging.yaml:16-29` configures `app.reputation_sucker.process_factions`, `app.reputation_sucker.screen_capture`, and `app.reputation_sucker.rep_tracker`; no such package exists. Current modules live under `app.screen_processing`. The format does include logger/function/line data, which is good, but uses the logger path rather than the standards-requested bare filename.

**Impact:** intended module-specific levels do not apply, making OCR/capture diagnostics harder to tune. Operators may believe DEBUG/INFO overrides are active when they are not.

**Recommendation:** replace stale names with current module names and include `%(filename)s:%(lineno)d` in the formatter.

### Medium — background cleanup uses polling and has no shutdown mechanism

**Evidence:** `main.py:45-61` runs an infinite `while True` loop with a five-minute sleep, and `main.py:323-325` starts it as a daemon thread. There is no stop event or final cleanup.

**Impact:** graceful shutdown and deterministic testing are difficult. Polling is acceptable as a low-frequency housekeeping mechanism, but the worker should still be controllable.

**Recommendation:** use a `threading.Event.wait(interval)` loop and signal it during application shutdown. Consider performing cleanup after screenshot writes plus a slow safety-net cleanup rather than relying solely on polling.

### Medium — very large components/modules concentrate unrelated responsibilities

**Evidence:** `frontend/src/pages/Dashboard.jsx` is about 1,024 lines; `app/screen_processing/process_system_targets.py` about 1,068; `app/screen_processing/screen_capture.py` about 862; and `process_territory_capture.py` about 703. Dashboard combines charting, manual entries, capture actions, calendar auth, scheduling CRUD, and modal UI. OCR modules combine navigation, image processing, persistence coordination, and scoring.

**Impact:** changes have a large regression surface, logic is difficult to test independently, and state/error handling becomes inconsistent.

**Recommendation:** extract Dashboard sections into focused components and API hooks/services. Split OCR code into pure detection/parsing/scoring units and orchestration classes. Do this incrementally around tests, not as a single rewrite.

### Low — type-hint coverage is inconsistent with project standards

**Evidence:** many public functions and methods lack parameter and return annotations, including `Database` methods, Flask handlers, models, several DAOs, and screen-processing functions. Examples include `app/database/database.py:30-101`, `app/models/*.py`, and `app/views/factions_view.py`.

**Impact:** refactoring and contract review rely on runtime knowledge, and defects in dynamic data shapes are easier to miss.

**Recommendation:** add annotations when touching modules, beginning with service/DAO boundaries and structured result types. Use `TypedDict` or Pydantic models for repeated dictionary shapes.

### Low — repository contains unusually large or misplaced tracked assets

**Evidence:** tracked files include `app/screen_snippets/favicon.zip` (~2.9 MB), `frontend/public/favicon.svg` (~2.2 MB), icon templates over 1 MB, root `Territory.jpg`, and images under tracked `tmp/`. The root also has a tiny unrelated `package-lock.json` while the actual frontend has its own manifest/lock.

**Impact:** clones and reviews are heavier, `tmp/` no longer communicates temporary status, and duplicate/misplaced package metadata is confusing.

**Recommendation:** verify which assets are runtime requirements; move durable fixtures to a named fixture/assets directory, remove obsolete archives/templates through a recoverable reviewed change, and delete the root lockfile if no root Node project exists. Optimize oversized web images, especially the SVG.

## Additional observations

- `reputations_view.py` correctly validates table names against the loaded DAO registry before interpolating them into SQL. Preserve this allowlist boundary.
- Database DAOs generally use `with self.db.connect()`; the context manager commits, rolls back, and closes connections reliably.
- API exception handlers usually log server details while returning generic 500 messages. A few domain `ValueError` messages are returned directly; keep those messages intentionally user-safe.
- `territory_view._annotate_with_calendar` silently swallows all exceptions (`app/views/territory_view.py:23-28`). Calendar failure is intentionally non-fatal, but it should at least log at debug/warning level so degraded behavior is diagnosable.
- File upload checks use `secure_filename` and an extension allowlist, which prevents straightforward traversal. Add content verification and a request-size cap because extension checks alone do not establish that content is a safe image.
- React hooks reviewed are declared before component return paths. The Combat refresh timer clears before reassignment and on cleanup, matching the timer-ref standard.
- Axios is used for frontend writes, so non-2xx responses reject automatically; several catch blocks only log to the console, however, leaving users without actionable feedback.
- The current `settings.yaml` is tracked while `.env`, Google credential files, captured community data, server logs, and build products are ignored. Keep secrets out of `settings.yaml`; consider tracking only `settings.yaml.example` if settings become machine-specific.

## Verification performed

- `npm run build` in `frontend/`: **passed** (416 modules transformed).
- `.venv\Scripts\python.exe -m compileall -q main.py config.py launcher.py app`: **passed**.
- Production configuration probe: **failed as expected**, demonstrating that `ProductionConfig.SECRET_KEY` resolves to a `property` object.
- Git/worktree review: existing untracked files under `frontend/src/components/ContextMenu/` and `frontend/src/components/HostileTemplateCapture/index.js` were present before this review and were not modified.
- Live database/API/OAuth/OCR/Windows automation/Docker/installer verification: **not performed**; these remain explicit verification gaps.

## Recommended remediation order

1. Fix production configuration and add a regression test for exact environment loading.
2. Restrict listeners to loopback by default; define and implement authentication for any intentional remote access.
3. Enforce request/body size limits and make community payload persistence concurrency-safe.
4. Add schema validation to mutation/control endpoints, including bounds and domain constraints.
5. Make faction creation atomic with dynamic DAO/table lifecycle—or remove unsupported runtime creation.
6. Establish PostgreSQL-backed integration tests and versioned migrations.
7. Correct port/logging documentation and add `.gitattributes`.
8. Refactor the largest modules incrementally behind tests and clean obsolete repository assets.

## Conclusion

The application’s core shape is sensible for a Windows-focused personal tracker, and recent code shows awareness of connection lifecycle, dynamic-identifier safety, and container/platform separation. Its present deployment defaults, configuration bug, and lack of boundary tests are the main barriers to reliability. Resolving the first five items above would materially improve both safety and day-to-day maintainability without requiring a broad rewrite.
