# CommuteOS

A personal mobility decision engine — not a transit app. It learns a commuter's routing preferences (speed vs. reliability, walking tolerance, transfer aversion) and proactively recommends real-time travel decisions. Starting domain: NYC-metro transit (MTA, NJ Transit, PATH).

Full product rationale lives in [`CommuteOS PRD.txt`](./CommuteOS%20PRD.txt). Open decisions and pending items are tracked in [`OPEN_QUESTIONS.md`](./OPEN_QUESTIONS.md).

**Scope decisions:** NYC-metro only (no plans to expand to other cities); a real multi-user product with accounts starting in Phase 2, not a single-user personal tool.

## Current phase

**Phase 1 — Real-Time Multi-Agency Transit Intelligence** (mostly done; NJ Transit still pending approval). **Phase 2 — Personal Commute Memory** (done: learned preferences, nightly-job stand-in). **Phase 3 — AI Commute Agent** (done: deterministic decision engine, LLM phrasing, recommendation tracking).

All three phases have working code end-to-end as of this rapid-build round — this does NOT mean Phase 1's real exit criteria are met (two weeks of daily personal use hasn't happened) or Phase 3's cold-start requirement is satisfied (no real 2-week trip history exists yet, only a synthetic demo seed - see `backend/app/jobs/seed_demo_trips.py`). "Built" and "validated against real usage" are different claims; see `OPEN_QUESTIONS.md` for what's still genuinely open.

## Status

- Flutter project scaffolded (`flutter create`), package id `com.commuteos.commuteos`
- Dev toolchain verified working: Flutter 3.44.8 (stable), JDK 17, Android SDK (build-tools 36.0.0), `flutter doctor` clean for Android target
- **Cross-agency architecture** (`lib/transit/`) — a `TransitStation`/`TransitService`/`TransitArrival` abstraction so search, favorites, and the arrivals screen work identically regardless of agency. Each agency (`lib/mta/`, `lib/path/`) adapts its own data shape (GTFS-RT protobuf, PATH's JSON) to these interfaces; a feed failure in one agency can't affect another.
- **MTA live subway arrivals working end-to-end** (`lib/mta/`) — fetches the unauthenticated MTA GTFS-realtime feed, parses the protobuf `TripUpdate`s, and renders live arrivals.
- **PATH live arrivals** (`lib/path/`) — all 13 PATH stations, fetched from the same (unofficial, unauthenticated) JSON endpoint that powers PATH's own website. No official public PATH API exists — see `OPEN_QUESTIONS.md` for the sourcing rationale. Includes staleness detection: if the feed's own timestamps go stale, the UI shows a "live data unavailable" banner rather than presenting old data as current.
- **All ~509 stations (MTA + PATH) searchable in one unified list, correctly grouped and sorted** — bundles MTA's published station list (`assets/data/mta_stations.csv`) plus PATH's 13 hardcoded stations; tapping a station shows live arrivals split into direction tabs. Verified on an Android emulator against the real feed for multiple stations. Stations sort in natural numeric order (1, 2, 3…96, 103, 110, not string order), and station names that map to more than one physical station (e.g. multiple "Canal St"s, some connected, some not) show as a single grouped row with a picker on tap rather than duplicate rows.
- **Favorites** (`lib/favorites/`) — the app opens to a favorites list (local device storage only, no account/backend), with an empty state prompting a first search. Favorite/unfavorite a whole station via a star icon, shared between the favorites view and the full search screen so both stay in sync. Favorites are keyed per-agency-per-station so an MTA and a PATH station can never collide.
- **Backend** (`backend/`) — FastAPI + SQLAlchemy 2.0 + Alembic, matching the PRD's `users`/`trips`/`preferences` schema, running against a real local PostgreSQL instance (installed and verified — see `OPEN_QUESTIONS.md` for the setup story). Auth: bcrypt + JWT, `/auth/signup`, `/auth/login`, `/users/me`. Every signup gets a `preferences` row at PRD defaults immediately.
- **Mobile app talks to the backend** (`lib/account/`) — an optional account screen (signup/login/logout), reachable from the favorites screen's app bar; browsing and favoriting still never require an account. Logging in turns on passive trip logging: opening any station's arrivals screen posts a trip data point to the backend for logged-in users only. `dest_stop` is left null since the app doesn't yet capture a real destination. Reaches the backend over USB (`adb reverse`) during development, not Wi-Fi — see `OPEN_QUESTIONS.md` for why.
- **Phase 2 — learned preferences** (`backend/app/preference_engine.py`, `GET/POST /preferences/me`) — a nightly-batch-job stand-in (run manually via `python -m app.jobs.recompute_preferences` for now; real OS-level scheduling is a deployment concern, not solved here) that recomputes `walking_tolerance_m` from trip history. `transfer_aversion_score` is deliberately left at its neutral default — the PRD's real signal for it (direct-vs-transfer route comparisons) doesn't exist in the data model yet, and computing a fake number would be worse than an honest "not yet knowable." A seed script (`backend/app/jobs/seed_demo_trips.py`) generates realistic synthetic trip history for demoing, since no real 2-week usage history exists yet. Flutter: a "What CommuteOS has learned" screen shows the plain-data numbers, per Phase 2's exit criteria.
- **Phase 3 — AI Commute Agent** (`backend/app/decision_engine.py`, `backend/app/llm_phrasing.py`, `POST /recommendations`) — MTA and PATH real-time fetching ported to Python (`backend/app/transit/`, verified against live feeds) so the backend can score candidate routes itself, matching the PRD's architecture. The decision engine is deterministic (no LLM), scoring candidates by predicted arrival time weighted by the user's `reliability_pref` against each route's confidence (live vs. stale data — a documented, scoped-down stand-in for the PRD's "recent delay variance," which isn't computable yet from current trip data). The LLM phrasing layer (Groq, OpenAI-compatible API) turns the engine's structured output into one sentence, never sees raw trip history, and falls back to a deterministic template if no API key is configured (none is yet — user has a Groq key to add later). `PATCH /trips/{id}/outcome` and `GET /trips/accuracy` implement the PRD's trust-preserving design (track whether recommendations were followed and how accurate they were). Flutter: a "What should I take?" screen lets the user pick 2+ favorited stations to compare.
- **NJ Transit scaffolded, not implemented** (`backend/app/transit/njt.py`) — still blocked on developer account approval. Deliberately doesn't guess a wire format: research surfaced real uncertainty (legacy SOAP/XML for rail vs. an unconfirmed format for bus, unlike MTA's protobuf or PATH's JSON), so the scaffold raises `NotImplementedError` rather than pretending to work until real credentials let the actual shape be verified, the same way MTA/PATH were each checked against live responses before their parsers were written.

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
.venv\Scripts\python -m alembic upgrade head   # requires a running local Postgres (see below)
.venv\Scripts\python -m uvicorn app.main:app --port 8001 --reload
```

Runs on **port 8001**, not FastAPI's usual 8000 default — this dev environment already has an unrelated project on 8000. Requires a local PostgreSQL instance with a `commuteos`/`commuteos` user and database (`CREATE USER commuteos WITH PASSWORD 'commuteos'; CREATE DATABASE commuteos OWNER commuteos;`), matching `DATABASE_URL` in `.env.example`.

To reach this from a physical Android phone during development (the app's `apiBaseUrl` in `lib/account/api_config.dart` points at `localhost:8001`): plug the phone in via USB and run `adb reverse tcp:8001 tcp:8001` once per session before testing signup/login/trip logging — browsing and favorites work fine without this, since they never call the backend.

## Tech stack (per PRD)

- Mobile: Flutter
- Backend (Phase 2+): FastAPI + PostgreSQL
- AI (Phase 3+): LLM used only for phrasing structured decision-engine output into natural language, never for the decision itself
- Maps: MapLibre + OSM
- Data: GTFS-RT, isolated per-agency parsers so one feed breaking doesn't break the others
