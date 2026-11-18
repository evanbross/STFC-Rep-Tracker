# STFC Rep Tracker — Full Project Code Review

**Review date:** 2026-11-17  
**Standards baseline:** all files listed by `AGENTS.md`, including the Codex session rules and review checklist referenced by `CODEX_CODING_STANDARDS.md`  
**Scope:** Flask API, PostgreSQL schema and DAOs, Windows/OCR automation, React SPA, Google Calendar integration, configuration, packaging, Docker, tests, documentation, and repository hygiene

## Executive summary

The project is in substantially better condition than it was at the 2026-11-03 review. Typed settings and request models, centralized error handling, versioned migrations, connection pooling, contract tests, safer filesystem paths, CSRF-origin checks, signal-driven screenshot retention, and the frontend decomposition are all present. The complete test suite passed against the configured disposable PostgreSQL database, and the React production build passed.

No critical defect was found. Two high-priority issues remain: migration 5 can prevent an older installation from starting if it contains a state the old schema explicitly allowed, and the Docker default publishes an unauthenticated mutation API to every host interface. The snippet upload lifecycle also has a concrete deletion bug: deleting the database row leaves the uploaded file in place, so the same filename can never be uploaded again.

**Overall assessment:** healthy for its intended single-user, loopback-bound Windows workflow, with good automated backend coverage. The Docker exposure and migration upgrade behavior should be corrected before treating every supported deployment path as safe and reliable.

## Findings

### High — migration 5 can fail upgrades from valid legacy data

**Evidence:** `app/database/migrations.py:206-216` adds a unique constraint on `(faction_code, timestamp)` with no preflight query, duplicate reconciliation, or actionable diagnostic. The preceding schema allowed duplicates. The comment at lines 208-210 records that one production database had no duplicates, but that observation is not an invariant for every existing installation. The migration tests cover an empty schema and the configured production-copy fixture, not a pre-v5 database containing duplicates.

**Impact:** any older database that acquired two readings for one faction at the same timestamp will fail `ALTER TABLE ... ADD CONSTRAINT`, roll back initialization, and prevent the application from starting. This is especially relevant because uniqueness was introduced specifically to replace an application-level concurrency strategy.

**Recommendation:** make the migration define its behavior for legacy duplicates. Either stop with a targeted diagnostic that identifies the conflicting keys and explains the repair, or deterministically reconcile them before adding the constraint. Add a real-PostgreSQL migration test starting at version 4 with duplicate rows and assert the chosen behavior.

### High — Docker publishes unauthenticated mutation endpoints on all interfaces

**Evidence:** `docker-compose.yml:21-22` maps `7300:7300`, which publishes on every host interface by default, and `Dockerfile:44-46` binds Gunicorn to `0.0.0.0:7300`. The application has no authentication layer. The API includes data mutation, snippet upload, calendar, community capture, and configuration-related operations. The Origin/Referer guard protects browser-based cross-origin writes; it does not authenticate curl, native clients, or another machine on the LAN.

**Impact:** on a host whose firewall permits the port, another machine can read and mutate tracker data without credentials. This contradicts the otherwise sound decision to keep the normal Windows and community-mod listeners loopback-only.

**Recommendation:** publish Compose to loopback by default (`127.0.0.1:7300:7300`). If LAN access is an intended supported mode, make it an explicit opt-in and add authentication/authorization before documenting it as safe.

### Medium — deleting an uploaded selected snippet leaves an undeletable orphan file

**Evidence:** upload writes the file at `app/views/factions_view.py:64-70`. The DELETE handler at lines 81-87 deletes only the database row. Upload rejects any filename that already exists on disk at lines 59-62.

**Impact:** after a user deletes an uploaded snippet, the image remains in the runtime snippet directory and the same filename always returns 409 on a later upload. Repeated use accumulates orphaned files. Removing files indiscriminately would also be unsafe because bundled snippets must remain intact, so ownership needs to be checked explicitly.

**Recommendation:** return the deleted row's filename from the DAO and remove the file only when it is a user-owned runtime snippet and no remaining row references it. Keep the database/file operation failure behavior explicit, and add an API test covering upload → delete → re-upload with the same filename.

### Medium — snippet uploads have no body-size or image-content validation

**Evidence:** `app/views/factions_view.py:35-78` accepts multipart uploads without a per-route/application size cap. It validates only the sanitized filename extension at lines 52-57, then streams the content directly to the destination at line 65. The main Flask app intentionally has no global `MAX_CONTENT_LENGTH`; only the separate community-mod app sets one.

**Impact:** a client can consume arbitrary disk space or save non-image content under an image extension. The latter can later produce confusing OpenCV failures. The Docker deployment increases the relevance of the resource-exhaustion path.

**Recommendation:** set a route-appropriate upload limit and decode/verify the image before committing it to the runtime snippet store. Write to a temporary file, validate, then atomically move it into place. Test missing length/chunked input as well as an invalid image with a valid extension.

### Medium — auto-selected backend ports can diverge from fixed consumers

**Evidence:** `launcher.py:148-160` chooses the next free port, including an arbitrary OS-assigned fallback, and lines 462-472 pass it to the backend. Meanwhile `frontend/vite.config.js:15-20` always proxies to `127.0.0.1:7300`, and the default CORS/documentation values also name 7300. The shared Caddy registration described in `CLAUDE.md` handles the launcher’s normal UI path, but the repository still presents the Vite workflow and port override as supported paths.

**Impact:** when 7300 is occupied, the launcher reports a successful start while a separately running Vite frontend continues sending API requests to 7300. This is the silent runtime-value divergence prohibited by the common standards.

**Recommendation:** use one authoritative port source for the backend and Vite proxy (for example a shared environment variable consumed by both). If a dependent cannot learn the selected port, fail fast rather than silently selecting a different one for that workflow.

### Medium — API models silently accept unknown request fields

**Evidence:** the shared request base sets `extra="ignore"` at `app/views/request_models.py:62-65`. This applies to mutation and automation bodies as well as queries. The comment says this accommodates a Factions form sending an `id` alias, but it weakens every other boundary model.

**Impact:** misspelled or obsolete fields receive a success response while being discarded. A client can believe it changed a value that the server never processed, making frontend/backend contract drift hard to diagnose.

**Recommendation:** default boundary models to `extra="forbid"`. Handle the one known Factions compatibility field explicitly with an alias or a narrowly scoped model setting, and add contract tests that reject unknown keys on state-changing routes.

### Medium — the Docker dependency manifest is a separate, drifting source of truth

**Evidence:** `requirements-docker.txt` is manually maintained separately from `pyproject.toml`, `uv.lock`, and the generated `requirements.txt`. Versions already differ (for example Requests and several transitive dependencies), and the Docker manifest contains packages not represented as direct project dependencies. Nothing in the build verifies that the container export matches the lock.

**Impact:** local/test and container environments can resolve materially different dependency graphs. A fix verified under `uv run pytest` may not describe the deployed container, and security/reproducibility updates can land in one manifest but not the other.

**Recommendation:** generate the lean Docker requirements from the same lock in a documented command, or define a locked dependency group/extra for the API-only container. Add a CI check that regeneration produces no diff.

### Low — frontend automation stops at compilation

**Evidence:** `frontend/package.json:6-9` defines dev/build/preview only. There is no lint, unit-test, or component-test command. The Vite production build passes, but it cannot validate conditional interactions, API error states, hook behavior, accessibility, or undefined names reached only in runtime branches.

**Impact:** the backend has broad regression coverage while frontend behavior depends mainly on manual browser checks. The largest remaining risk is not syntax but user interaction and frontend/backend contract drift.

**Recommendation:** add ESLint with React Hooks rules and a focused Vitest/Testing Library suite for the API hooks and highest-value flows (capture busy/error handling, faction editing, history loading, and Spock's Club preview/import).

### Low — frontend package metadata conflicts with the repository license

**Evidence:** `frontend/package.json:13` declares `"license": "ISC"`, while source headers and the root `LICENSE` declare PolyForm Strict 1.0.0.

**Impact:** packaging and license scanners report contradictory terms for the frontend package.

**Recommendation:** set the package metadata to the correct SPDX identifier (`PolyForm-Strict-1.0.0`) or use `UNLICENSED` if this package is intentionally private and not independently distributed.

### Low — type annotations remain incomplete at important Flask boundaries

**Evidence:** multiple route functions still omit parameter and return annotations; examples include `app/views/factions_view.py:29`, `:36`, `:82`, and the `MethodView` handlers in `app/views/status_entries_view.py`. The Python standards require annotations on function signatures.

**Impact:** the runtime behavior is unaffected, but refactors and contract review get less static help precisely at HTTP boundaries where shapes matter most.

**Recommendation:** annotate route parameters and use `ResponseReturnValue` (or a narrower applicable type) for handlers as files are touched. Add a type checker only after establishing a realistic baseline; do not suppress the backlog with broad ignores.

## Positive observations

- All source files sampled under `app/` and `frontend/src/` carry the required license header, and the root license exists.
- `.gitattributes` enforces the required CRLF checkout policy for this Windows project.
- Logging includes timestamp, level, logger, filename, and line number.
- Request bodies are centrally parsed through Pydantic and validation errors are sanitized.
- SQL values are parameterized; dynamic identifiers reviewed are constrained by allowlists or discovered DAO metadata.
- Database connections are managed through context managers with commit/rollback/return-to-pool behavior.
- Schema DDL is centralized in numbered migrations rather than DAO table-creation methods.
- Google interactive authentication is confined to the explicit connect endpoint; background reads do not launch OAuth.
- React hooks reviewed appear before early returns, and the Combat timer is cleared before reassignment and on cleanup.
- Frontend writes go through a shared Axios client, so non-2xx responses reject rather than silently refetching stale state.
- The prior large Dashboard and parsing modules have been decomposed into focused components/hooks and pure parsing modules with tests.

## Verification performed

- `uv run pytest -q`: **passed — 343 tests in 102.66 seconds**, including the configured real-PostgreSQL tests (no skips were reported).
- `npm run build` in `frontend/`: **passed — 438 modules transformed**.
- `uv run ruff check .`: **not run — Ruff is not declared/installed** (`program not found`). This is a tooling gap, not a test failure.
- Manual standards searches covered broad exception handlers, local-time APIs, stubs/TODOs, timers, dynamic SQL, transaction calls, private imports, source headers, environment variables, ports, and dependency manifests.
- Git worktree was clean before this report was created.

## Verification gaps

The following boundaries were reviewed statically but were not exercised during this review:

- live STFC window navigation, OCR accuracy, mouse/keyboard automation, and long-running away-team/gift loops;
- live Google OAuth and Calendar API behavior;
- PyInstaller build, Inno installer, elevation/relaunch, and reinstall persistence;
- Docker image build/run and network/firewall behavior;
- browser-level interaction and accessibility checks;
- upgrade of a real pre-v5 database containing duplicate status entries.

## Recommended remediation order

1. Define and test migration-5 behavior for legacy duplicates.
2. Bind the default Compose publication to loopback, or add authentication for intentional remote access.
3. Fix the selected-snippet delete lifecycle and add size/content validation to uploads.
4. Unify dynamic port configuration across the launcher and Vite development proxy.
5. Forbid unknown fields by default at API boundaries, with narrow compatibility exceptions.
6. Generate Docker dependencies from the authoritative lock and enforce no-drift checks.
7. Add frontend linting and focused interaction tests.
8. Correct package license metadata and incrementally complete boundary type annotations.

## Conclusion

The current codebase is well beyond the “functional but not production-hardened” state described two weeks ago. Its core database, API-validation, error-handling, and frontend structure are now coherent and backed by a meaningful automated suite. The remaining work is concentrated at deployment and lifecycle edges rather than spread throughout the core. Addressing the first three items would remove the most credible upgrade, exposure, and user-visible data-management failures without requiring architectural churn.
