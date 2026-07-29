# Open Questions & Pending Decisions

Running list of unresolved questions for CommuteOS. Ask "what's pending?" any time to get a current read.

## Unresolved

- [ ] **iOS timeline** — PRD specifies Android-first (Flutter). Is iOS ever in scope, or Android-only for the foreseeable future?
- [ ] **Geographic scope** — Is CommuteOS permanently NYC-metro (MTA/NJT/PATH), or should Phase 1 architecture anticipate other metro areas?
- [ ] **User model for Phase 2+** — Is this a single-user personal tool (just for the builder's own commute) or a multi-user product with auth/accounts? Affects the `users` table design and whether auth needs to be built at all.
- [ ] **Backend hosting/infra** — Where does FastAPI + PostgreSQL run for Phase 2 (local dev only, a cheap cloud host, something else)? Not urgent until Phase 2 starts.
- [ ] **NJ Transit developer registration** — IN PROGRESS (2026-07-27): user is submitting the developer portal application now. Blocks only the NJ Transit feed/parser specifically — MTA and PATH work continues in parallel. Follow up once API key/credentials arrive to wire up the NJ Transit parser module.
- [ ] **Favorites design** — PRD calls for favorite stations/routes (local device storage, Phase 1). Now that search/browse exists, where do favorites live in the UI — a star icon per station row pinning it to the top of the list, a separate tab, or something else? Also: favorite a whole station, or a specific direction/platform within it?
- [ ] **Static station data refresh strategy** — `assets/data/mta_stations.csv` is a point-in-time snapshot bundled into the app. MTA updates this rarely, but when a station opens/closes/renames the app won't know until this asset is manually refreshed and the app rebuilt. Fine for now — worth revisiting if this becomes a real maintenance burden.

## Resolved

- [x] **Flutter/Android dev toolchain** (resolved 2026-07-28) — JDK 17, Flutter SDK 3.44.8 (stable), Android Studio + SDK (cmdline-tools, platform-tools, build-tools 36.0.0), Windows long path support, and Android SDK licenses are all installed/accepted. `flutter doctor` clean except Visual Studio (Windows desktop dev), which is irrelevant since we're targeting Android only.
- [x] **Repo hosting** (resolved 2026-07-28) — Public GitHub repo created at github.com/kshitijmodi/CommuteOS, initial Flutter scaffold committed and pushed. Note: `CommuteOS/` was previously a subfolder inside a git repo rooted at the whole Downloads folder (mixed with unrelated personal files) — it now has its own independent `.git`, unaffected by that parent repo.
- [x] **MTA GTFS-RT integration** (resolved 2026-07-28) — Confirmed MTA subway feeds are public/unauthenticated (no API key needed, unlike some outdated docs suggest). Built `lib/mta/` (feed URLs, protobuf parsing via `gtfs_realtime_bindings`, a live-arrivals screen) and verified against the real feed on an Android emulator (`commuteos_test` AVD, API 35). Uses the base GTFS-RT spec only — not MTA's NYCT-specific proto extension (train assigned/unassigned status) — which is sufficient for Phase 1's basic arrival-time display.
- [x] **All-station search + correctness bug caught** (resolved 2026-07-28) — Initial hardcoded-station build used a wrong stop_id (`R16N`, which is actually Times Sq, not Union Square as labeled) — the pipeline worked but showed the wrong station's data under the wrong label. Fixed by building real station data support: bundled MTA's `Stations.csv` (496 stations, pre-joined with routes and direction labels) as a local asset, parsed via the `csv` package, added a route→realtime-feed lookup table (not derivable from static GTFS, hardcoded ~30 entries), and rebuilt the home screen as a searchable station list. Verified multiple stations and both direction tabs against live data on the emulator.
