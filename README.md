# CommuteOS

A personal mobility decision engine — not a transit app. It learns a commuter's routing preferences (speed vs. reliability, walking tolerance, transfer aversion) and proactively recommends real-time travel decisions. Starting domain: NYC-metro transit (MTA, NJ Transit, PATH).

Full product rationale lives in [`CommuteOS PRD.txt`](./CommuteOS%20PRD.txt). Open decisions and pending items are tracked in [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md).

## Current phase

**Phase 1 — Real-Time Multi-Agency Transit Intelligence.** No backend, no recommendations yet. Goal is a working Android app that surfaces live MTA/NJ Transit/PATH data reliably. Exit criteria: daily personal use for two weeks without falling back to the official agency apps.

## Status

- Flutter project scaffolded (`flutter create`), package id `com.commuteos.commuteos`
- Dev toolchain verified working: Flutter 3.44.8 (stable), JDK 17, Android SDK (build-tools 36.0.0), `flutter doctor` clean for Android target
- **Cross-agency architecture** (`lib/transit/`) — a `TransitStation`/`TransitService`/`TransitArrival` abstraction so search, favorites, and the arrivals screen work identically regardless of agency. Each agency (`lib/mta/`, `lib/path/`) adapts its own data shape (GTFS-RT protobuf, PATH's JSON) to these interfaces; a feed failure in one agency can't affect another.
- **MTA live subway arrivals working end-to-end** (`lib/mta/`) — fetches the unauthenticated MTA GTFS-realtime feed, parses the protobuf `TripUpdate`s, and renders live arrivals.
- **PATH live arrivals** (`lib/path/`) — all 13 PATH stations, fetched from the same (unofficial, unauthenticated) JSON endpoint that powers PATH's own website. No official public PATH API exists — see `OPEN_QUESTIONS.md` for the sourcing rationale. Includes staleness detection: if the feed's own timestamps go stale, the UI shows a "live data unavailable" banner rather than presenting old data as current.
- **All ~509 stations (MTA + PATH) searchable in one unified list, correctly grouped and sorted** — bundles MTA's published station list (`assets/data/mta_stations.csv`) plus PATH's 13 hardcoded stations; tapping a station shows live arrivals split into direction tabs. Verified on an Android emulator against the real feed for multiple stations. Stations sort in natural numeric order (1, 2, 3…96, 103, 110, not string order), and station names that map to more than one physical station (e.g. multiple "Canal St"s, some connected, some not) show as a single grouped row with a picker on tap rather than duplicate rows.
- **Favorites** (`lib/favorites/`) — the app opens to a favorites list (local device storage only, no account/backend), with an empty state prompting a first search. Favorite/unfavorite a whole station via a star icon, shared between the favorites view and the full search screen so both stay in sync. Favorites are keyed per-agency-per-station so an MTA and a PATH station can never collide.
- Next up: NJ Transit (pending user's developer registration — see `OPEN_QUESTIONS.md`)

## Getting started

```
flutter pub get
flutter run
```

Requires the Flutter SDK and Android SDK on PATH — see `flutter doctor` to verify your environment.

## Tech stack (per PRD)

- Mobile: Flutter
- Backend (Phase 2+): FastAPI + PostgreSQL
- AI (Phase 3+): LLM used only for phrasing structured decision-engine output into natural language, never for the decision itself
- Maps: MapLibre + OSM
- Data: GTFS-RT, isolated per-agency parsers so one feed breaking doesn't break the others
