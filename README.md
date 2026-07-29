# CommuteOS

A personal mobility decision engine — not a transit app. It learns a commuter's routing preferences (speed vs. reliability, walking tolerance, transfer aversion) and proactively recommends real-time travel decisions. Starting domain: NYC-metro transit (MTA, NJ Transit, PATH).

Full product rationale lives in [`CommuteOS PRD.txt`](./CommuteOS%20PRD.txt). Open decisions and pending items are tracked in [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md).

**Scope decisions:** NYC-metro only (no plans to expand to other cities); a real multi-user product with accounts starting in Phase 2, not a single-user personal tool.

## Current phase

**Phase 1 — Real-Time Multi-Agency Transit Intelligence** (mostly done; NJ Transit still pending). **Phase 2 — Personal Commute Memory** (backend scaffolding started).

Phase 1 exit criteria: daily personal use for two weeks without falling back to the official agency apps.

## Status

- Flutter project scaffolded (`flutter create`), package id `com.commuteos.commuteos`
- Dev toolchain verified working: Flutter 3.44.8 (stable), JDK 17, Android SDK (build-tools 36.0.0), `flutter doctor` clean for Android target
- **Cross-agency architecture** (`lib/transit/`) — a `TransitStation`/`TransitService`/`TransitArrival` abstraction so search, favorites, and the arrivals screen work identically regardless of agency. Each agency (`lib/mta/`, `lib/path/`) adapts its own data shape (GTFS-RT protobuf, PATH's JSON) to these interfaces; a feed failure in one agency can't affect another.
- **MTA live subway arrivals working end-to-end** (`lib/mta/`) — fetches the unauthenticated MTA GTFS-realtime feed, parses the protobuf `TripUpdate`s, and renders live arrivals.
- **PATH live arrivals** (`lib/path/`) — all 13 PATH stations, fetched from the same (unofficial, unauthenticated) JSON endpoint that powers PATH's own website. No official public PATH API exists — see `OPEN_QUESTIONS.md` for the sourcing rationale. Includes staleness detection: if the feed's own timestamps go stale, the UI shows a "live data unavailable" banner rather than presenting old data as current.
- **All ~509 stations (MTA + PATH) searchable in one unified list, correctly grouped and sorted** — bundles MTA's published station list (`assets/data/mta_stations.csv`) plus PATH's 13 hardcoded stations; tapping a station shows live arrivals split into direction tabs. Verified on an Android emulator against the real feed for multiple stations. Stations sort in natural numeric order (1, 2, 3…96, 103, 110, not string order), and station names that map to more than one physical station (e.g. multiple "Canal St"s, some connected, some not) show as a single grouped row with a picker on tap rather than duplicate rows.
- **Favorites** (`lib/favorites/`) — the app opens to a favorites list (local device storage only, no account/backend), with an empty state prompting a first search. Favorite/unfavorite a whole station via a star icon, shared between the favorites view and the full search screen so both stay in sync. Favorites are keyed per-agency-per-station so an MTA and a PATH station can never collide.
- NJ Transit still pending user's developer registration approval — see `OPEN_QUESTIONS.md`.
- **Phase 2 backend scaffolded** (`backend/`) — FastAPI + SQLAlchemy 2.0 + Alembic, matching the PRD's `users`/`trips`/`preferences` schema. Since Phase 2's user model decision landed on a real multi-user product (not a personal tool), `users` includes proper auth: email/password signup and login issuing JWT access tokens, a `/users/me` endpoint demonstrating the auth dependency. Every signup gets a `preferences` row created at PRD-specified defaults immediately, ready for the (not yet built) nightly batch job to update. 8 passing tests (SQLite in-memory, not Postgres — no Postgres-specific features are exercised yet). PostgreSQL itself isn't installed on the dev machine yet (see `OPEN_QUESTIONS.md`) so the Alembic migration is hand-written and syntax-checked but not yet run against a live database.

## Getting started

### Mobile app (Flutter)

```
flutter pub get
flutter run
```

Requires the Flutter SDK and Android SDK on PATH — see `flutter doctor` to verify your environment.

### Backend (FastAPI)

```
cd backend
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
copy .env.example .env    # then edit DATABASE_URL/SECRET_KEY as needed
.venv\Scripts\python -m pytest        # run tests (SQLite, no Postgres needed)
.venv\Scripts\python -m alembic upgrade head   # requires a running Postgres
.venv\Scripts\python -m uvicorn app.main:app --reload
```

## Tech stack (per PRD)

- Mobile: Flutter
- Backend (Phase 2+): FastAPI + PostgreSQL
- AI (Phase 3+): LLM used only for phrasing structured decision-engine output into natural language, never for the decision itself
- Maps: MapLibre + OSM
- Data: GTFS-RT, isolated per-agency parsers so one feed breaking doesn't break the others
