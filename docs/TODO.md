# To Do

Feature work and ideas not yet scheduled. Review findings live in the dated
`full-project-review-*.md` / `remediation-plan-*.md` files instead.


## Community mod sync in the installed app

*Added 2026-11-18; narrowed 2026-11-19 once mod payloads started updating reputation.*

The mod reaches the app at `http://stfc.localhost`, a Caddy name. `zt-common` is a
dev-only dependency and isn't in the installer build, so an installed copy has no
Caddy route and receives no mod sync. Decide whether the installed app needs it,
and if so how the mod finds it: a fixed localhost port, or a name some other way.
A picked port has to reach the mod's config from one source; see "Auto-Selected
Runtime Values Must Not Silently Diverge" in the common standards.
