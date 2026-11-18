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
