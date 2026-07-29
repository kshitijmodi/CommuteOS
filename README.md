# CommuteOS

A personal mobility decision engine — not a transit app. It learns a commuter's routing preferences (speed vs. reliability, walking tolerance, transfer aversion) and proactively recommends real-time travel decisions. Starting domain: NYC-metro transit (MTA, NJ Transit, PATH).

Full product rationale lives in [`CommuteOS PRD.txt`](./CommuteOS%20PRD.txt). Open decisions and pending items are tracked in [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md).

## Current phase

**Phase 1 — Real-Time Multi-Agency Transit Intelligence.** No backend, no recommendations yet. Goal is a working Android app that surfaces live MTA/NJ Transit/PATH data reliably. Exit criteria: daily personal use for two weeks without falling back to the official agency apps.

## Status

- Flutter project scaffolded (`flutter create`), package id `com.commuteos.commuteos`
- Dev toolchain verified working: Flutter 3.44.8 (stable), JDK 17, Android SDK (build-tools 36.0.0), `flutter doctor` clean for Android target
- **MTA live subway arrivals working end-to-end** (`lib/mta/`) — fetches the unauthenticated MTA GTFS-realtime feed, parses the protobuf `TripUpdate`s, and renders live arrivals for a hardcoded stop (Union Square, N/Q/R/W northbound). Verified on an Android emulator against the real feed.
- Next up: NJ Transit and PATH feeds (pending NJ Transit developer registration — see `OPEN_QUESTIONS.md`), then a station picker/map instead of the hardcoded stop

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
