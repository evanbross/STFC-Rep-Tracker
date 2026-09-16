# Frontend Code Review - 2026-06-15

Scope: `frontend/` source, Vite config, and frontend/backend API contract touchpoints. Review focused on correctness, user-visible failure modes, data integrity, and project React standards.

## Findings

### Medium - Quick reputation edits can send invalid or truncated values

The dashboard quick-edit input sends `parseInt(value)` directly to the API without validation or a radix. Empty input becomes `NaN`, which serializes to JSON as `null`; mixed input such as `123abc` is accepted as `123`. The UI then clears the field immediately even if the request fails.

References:
- `frontend/src/pages/Dashboard.jsx:222-224`
- `frontend/src/pages/Dashboard.jsx:568-585`
- `app/views/status_entries_view.py:126-136`

Impact: users can unintentionally submit bad data or get a generic failure after the input has already been cleared. Validate the parsed value with `Number.isFinite()`, reject empty/non-numeric input before posting, use `parseInt(value, 10)` or `Number(value)`, and clear the field only after a successful save.

### Medium - Territory schedule write failures have no user-visible handling

Several territory schedule actions perform mutating requests without local `try/catch` handling or error state. `saveScheduleEntry()`, `addToCalendar()`, and `deleteScheduleEntry()` all rely on Axios throwing on failure, but the event handlers do not catch those rejections or alert the user.

References:
- `frontend/src/pages/Dashboard.jsx:360-364`
- `frontend/src/pages/Dashboard.jsx:404-421`
- `frontend/src/pages/Dashboard.jsx:443-445`
- `app/views/territory_view.py:65-100`
- `app/views/territory_view.py:123-143`
- `app/views/territory_view.py:146-151`

Impact: API failures leave the modal in a stale state and surface only as console errors or unhandled promise rejections. Add explicit error handling around these writes, keep the form values intact on failure, and show a concise user-facing error.

### Medium - The initial frontend bundle eagerly includes every route and chart dependency

`App.jsx` imports `Dashboard`, `Factions`, and `Reputations` eagerly, and `Dashboard` imports Chart.js, the date adapter, and the annotation plugin at module load time. The production build succeeds, but Vite reports the main JavaScript chunk at `549.20 kB` minified (`177.53 kB` gzip), above its 500 kB warning threshold.

References:
- `frontend/src/App.jsx:35-37`
- `frontend/src/App.jsx:46-50`
- `frontend/src/pages/Dashboard.jsx:35-52`
- Verification: `npm run build` completed successfully and emitted the chunk-size warning.

Impact: visiting lightweight pages such as Factions or Reputations still downloads the dashboard chart stack up front. Use `React.lazy()`/`Suspense` for route-level splitting and consider isolating chart registration in the dashboard route chunk.

### Low - Snippet preview object URLs can leak until page reload

The snippet modal creates object URLs for selected and pasted images. `clearPending()` revokes the current preview URL, but replacing a pending file through the file picker or the global paste listener does not revoke the previous URL first, and closing the modal does not run cleanup for the current pending preview.

References:
- `frontend/src/pages/Factions.jsx:90-101`
- `frontend/src/pages/Factions.jsx:103-107`
- `frontend/src/pages/Factions.jsx:119-120`
- `frontend/src/pages/Factions.jsx:127-132`

Impact: repeated snippet previews can retain blob memory for the lifetime of the page. Revoke the existing `pendingFile.previewUrl` before replacing it and add a `useEffect` cleanup that revokes the current URL on modal unmount.

### Low - `confirm()` is used as an unqualified browser global

The snippet delete handler uses bare `confirm()` instead of `window.confirm()`, which violates the project React standards and is less explicit for linters/static analysis.

References:
- `frontend/src/pages/Factions.jsx:154-158`

Impact: this is minor, but easy to fix while touching the snippet modal. Use `window.confirm(...)`.

## Additional Notes

- `npm run build` in `frontend/` completed successfully.
- The Vite proxy currently targets `http://127.0.0.1:7300`, which matches `main.py`'s default `PORT` value. The project `AGENTS.md` overview still says the Flask API runs on port 7000, so that documentation appears stale.
- The worktree already had unrelated backend changes and untracked content before this report was written; this review did not modify those files.
