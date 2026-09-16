# App Folder Code Review - 2026-06-15

Scope: `app/` only. Review focused on correctness, security, data integrity, and project standards.

## Findings

### High - Reputation endpoints look up DAOs by the wrong key

`ReputationsDAO.initialize_dao_instances()` registers DAO instances under the faction display name (`faction.get("name")`), but several reputation routes look them up by table name strings such as `augment_reputations`, `fkr_reputations`, and `section31_reputations`.

References:
- `app/database/reputations_dao.py:114-146`
- `app/views/reputations_view.py:53-58`
- `app/views/reputations_view.py:61-98`
- `app/views/reputations_view.py:231-234`

Impact: routes like `GET /api/reputations/augment` can return "DAO not found" even when the DAO exists, and `GET /api/reputations/by-table/<table_name>` can pass validation but then call `get_all()` on `None`, returning a 500. The route lookup key and registry key need to be made consistent, or the registry should support both table names and faction names explicitly.

### High - Capture endpoints return HTTP 200 for failed capture operations

`_run_capture()` only maps exceptions to error status codes. Several capture paths return `{"error": ...}` as normal data instead of raising, so `_run_capture()` serializes those failures as `200 OK`.

References:
- `app/views/capture_screen_view.py:56-64`
- `app/screen_processing/process_reputations.py:82-111`
- `app/screen_processing/process_reputations.py:135-155`

Impact: clients cannot reliably distinguish success from failure by status code. For example, if the STFC window is missing, `_navigate_to_factions()` returns an error dict, `process_reputations()` returns it, and `_run_capture()` responds with 200. `_run_capture()` should inspect dict results for an `error` key or the orchestrators should raise typed exceptions for route-level mapping.

### Medium - Snippet upload can leave filesystem and database state inconsistent

`add_selected_snippet()` saves the uploaded file to disk before inserting the database row, and the DAO insert can fail afterward because `faction_id` is a foreign key. There is no rollback/removal of the already-written file. The endpoint also accepts any extension/content and overwrites an existing file with the same secured name.

References:
- `app/views/factions_view.py:63-83`
- `app/database/faction_selected_snippets_dao.py:81-90`
- `app/database/faction_selected_snippets_dao.py:40-47`

Impact: failed or duplicate uploads can create orphaned templates, replace existing snippets, or register unsupported files that later break OpenCV loading. Validate the faction before saving, restrict accepted image types, avoid overwriting existing filenames, validate `snippet_type`, and remove the saved file if the database insert fails.

### Medium - New/updated factions cannot set `reputation_dao_name` through the API

The DAO layer supports `reputation_dao_name`, and startup depends on that column to load the correct reputation DAO. The POST/PUT faction routes do not read `reputation_dao_name` from the request body or pass it to the DAO, so API-created or API-edited factions can silently lose the metadata required for dynamic DAO loading.

References:
- `app/views/factions_view.py:147-165`
- `app/views/factions_view.py:217-236`
- `app/database/factions_dao.py:139-178`
- `app/database/factions_dao.py:180-235`

Impact: adding a reputation type through the UI/API can create a faction row that looks mostly valid but cannot initialize its reputation DAO on restart. Include `reputation_dao_name` and the snippet fields in route validation/persistence, or make the API explicitly reject reputation-table changes unless the DAO metadata is supplied.

### Medium - External-service routes return raw exception text to clients

Several Google Calendar and territory endpoints return `str(e)` directly from broad exception handlers.

References:
- `app/views/calendar_view.py:54-58`
- `app/views/calendar_view.py:86-91`
- `app/views/territory_view.py:108-137`

Impact: errors from credentials files, local paths, OAuth failures, Google API responses, or connection details can be exposed to API clients. Project standards call for logging full exceptions server-side and returning sanitized client messages. Keep user-actionable messages for expected cases, but avoid raw exception text from broad handlers.

### Medium - Community mod capture persists full headers and arbitrary payloads without limits

`receive_payload()` accepts any JSON body, stores full request headers, and appends everything to `community-data.json` without authentication, content-length enforcement, field validation, or redaction.

References:
- `app/views/community_mod_view.py:78-109`

Impact: a caller can fill disk or persist sensitive headers such as cookies, authorization tokens, local IP details, or other mod-provided data. Add an expected schema/size limit, require a shared secret or local-only guard if this endpoint is not meant to be public, and redact sensitive headers before writing.

### Low - Some internal timestamps still use local time

The project standards require UTC for internal timestamps. Some capture/debug paths still use local-time `datetime.now()` for filenames or event derivation.

References:
- `app/screen_processing/screen_capture.py:604-605`
- `app/screen_processing/screen_capture.py:630-632`
- `app/screen_processing/process_reputations.py:262-268`
- `app/screen_processing/process_territory_capture.py:335-359`
- `app/screen_processing/process_territory_capture.py:419-454`
- `app/screen_processing/process_territory_capture.py:498-562`

Impact: filename ordering and derived event times can vary around timezone boundaries or when logs/artifacts are compared across machines. Use `datetime.now(UTC)` for internal timestamps unless a value is intentionally local UI/game time and documented as such.

## Additional Notes

- The `Database.connect()` context manager commits, rolls back, and closes connections reliably (`app/database/database.py:73-84`).
- Status-entry sort parameters are allowlisted before interpolation (`app/database/status_entries_dao.py:111-150` and `app/database/status_entries_dao.py:174-202`).
- The worktree already had unrelated untracked content before this report was written: `app/screen_snippets/Away Teams Refresh.jpg` and `tmp/`.
