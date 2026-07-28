# Open Questions & Pending Decisions

Running list of unresolved questions for CommuteOS. Ask "what's pending?" any time to get a current read.

## Unresolved

- [ ] **iOS timeline** — PRD specifies Android-first (Flutter). Is iOS ever in scope, or Android-only for the foreseeable future?
- [ ] **Geographic scope** — Is CommuteOS permanently NYC-metro (MTA/NJT/PATH), or should Phase 1 architecture anticipate other metro areas?
- [ ] **User model for Phase 2+** — Is this a single-user personal tool (just for the builder's own commute) or a multi-user product with auth/accounts? Affects the `users` table design and whether auth needs to be built at all.
- [ ] **Backend hosting/infra** — Where does FastAPI + PostgreSQL run for Phase 2 (local dev only, a cheap cloud host, something else)? Not urgent until Phase 2 starts.
- [ ] **NJ Transit developer registration** — IN PROGRESS (2026-07-27): user is submitting the developer portal application now. Blocks only the NJ Transit feed/parser specifically — MTA and PATH work continues in parallel. Follow up once API key/credentials arrive to wire up the NJ Transit parser module.

## Resolved

- [x] **Flutter/Android dev toolchain** (resolved 2026-07-28) — JDK 17, Flutter SDK 3.44.8 (stable), Android Studio + SDK (cmdline-tools, platform-tools, build-tools 36.0.0), Windows long path support, and Android SDK licenses are all installed/accepted. `flutter doctor` clean except Visual Studio (Windows desktop dev), which is irrelevant since we're targeting Android only.
