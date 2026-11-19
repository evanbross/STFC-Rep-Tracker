# To Do

Feature work and ideas not yet scheduled. Review findings live in the dated
`full-project-review-*.md` / `remediation-plan-*.md` files instead.

## Spock's Club live listener

*Added 2026-11-18.*

Add a listener that accepts data pushed from Spock's Club, register it with Caddy
under its own name, and update the database when reputation values have changed.
This would replace exporting a file and importing it by hand.

What already exists to build on:
- **Parsing and saving:** `app/spocks_club_parsing.py` reads an export, and
  `POST /api/spocks-club/import` saves readings through `status_entries.add_entries_at`,
  which skips a faction that already has a reading at that instant.
- **A second listener:** `main.py` already runs one for the community mod
  (`_run_community_mod_https_server`, port 7443, bound to `community_mod.bind_host`).
  It's the pattern to follow: its own small Flask app, its own thread, the
  cross-origin write guard, and a payload size cap.
- **Caddy registration:** `launcher.py` registers the main app as `stfc` via
  `zt_devkit.caddy_registry.register(name, port)`.

Open questions:
- **What does Spock's Club send, and how?** Is it a push to a URL, a webhook, or a
  socket? Does it send the same TSV as the export, or a different format? This
  decides whether the existing parser can be reused.
- **"When there has been a change":** should it save only factions whose value
  differs from their latest reading, or every reading and rely on the
  same-instant skip? Which timestamp should it use: the payload's, or the time it
  was received?
- **Caddy in the installed app:** `zt-devkit` is a dev-only dependency and isn't
  in the installer build, so a Caddy name only exists in a source checkout. Does
  the installed app need it too, or is a fixed localhost port enough there?
- **Port:** a fixed port (like 7443), or picked at startup like the main app? A
  picked port has to reach Spock's Club and Caddy from one source. See
  "Auto-Selected Runtime Values Must Not Silently Diverge" in the common standards.
- **Trust:** bind to loopback by default, like the community-mod listener. Does it
  need a shared secret if Spock's Club runs on another machine?
- **Refresh:** once a push saves new readings, notify the open Dashboard (SSE)
  rather than having it poll.

*Update 2026-11-18:* Spock's Club doesn't push data itself; it receives it from
the community mod's sync. The mod now also syncs to this app through Caddy (see
"Retire the 7443 community-mod listener" below), and its `resource` records
carry the same IDs as `factions.spocks_resource_id` (e.g. 970475396 =
Federation Points). The live listener is probably "save the mod's faction
resources" on the existing `/api/community-mod/` route, not a new listener.
That would answer the format, port and Caddy questions above.

## Check the community mod's sync token

*Added 2026-11-18.*

`POST /api/community-mod/` accepts any request. That's fine while it's only
reachable from this machine through `http://stfc.localhost`, but a cloud
deployment would expose it publicly.

- Add an optional `COMMUNITY_MOD_TOKEN` to `AppSettings`. When it's set,
  `receive_payload` rejects a request whose `stfc-sync-token` header doesn't match
  (compare with `hmac.compare_digest`). When it's unset, keep today's behaviour,
  so local use doesn't change.
- The header is already in `_SENSITIVE_HEADERS`, so it's never written to
  `community-data.jsonl`.
- The mod sends the `token` from its `[sync.targets.stfc-rep-tracker]` table in
  `community_patch_settings.toml` (currently the placeholder `"local"`).
- Settings errors must name the field, never the value (see `config.py`).

## Retire the 7443 community-mod listener

*Added 2026-11-18.*

The mod now syncs to `http://stfc.localhost/api/community-mod/`, which Caddy
proxies to the main app on whatever port it picked. Confirmed working
2026-11-18: payloads arrive with `Host: stfc.localhost`. The main app already
mounts `community_mod_bp` at `/api/community-mod`, so the separate HTTPS
listener on 7443 is no longer used.

Remove from `main.py`:
- `_run_community_mod_https_server`, `create_community_mod_app` and the thread that
  starts them.
- `_ensure_community_mod_cert` and its self-signed cert files. `main.py` is the only
  `cryptography` importer, so drop it from `pyproject.toml` too (if it's a direct
  dependency there, not just pulled in by another package), then `uv lock` and
  regenerate `requirements.txt`.
- The `community_mod.bind_host` setting in `settings.yaml` / `settings.yaml.example`,
  and the 7443 listener references in `CLAUDE.md` (cross-origin write guard
  section) and `community_mod_view.py`'s comments.
- The 7443-app cases in `tests/test_csrf_guard.py` (the main app's guard tests stay).

Keep: `community_mod_bp`, the payload size cap (`community_mod.max_payload_bytes`)
and `append_capture`.

Before removing it, check that nothing else still posts to `localhost:7443`. The
installed app has no Caddy (`zt-devkit` is dev-only), so this assumes the
installed build doesn't need mod sync, or will get its own route when it does.
