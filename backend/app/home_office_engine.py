"""Infers a user's home and office station from Trip history, per the
PRD's Phase 2 signal ("home/office location - inferred from most common
start/end points over ~5 trips, confirmed once via a simple prompt").

Scope note: this infers *stations*, not lat/lng coordinates - see the
User model's docstring for why. The underlying signal (where a commuter
usually starts and ends their day) is the same; only the representation
differs from the PRD's literal wording.

Heuristic: trips before noon are "morning" (commute FROM home), trips at
or after noon are "evening" (commute FROM office, heading home) - a
simple, explainable proxy, not a scheduling-ML model. home_station is the
most common origin_stop among morning trips; office_station is the most
common origin_stop among evening trips. Requires at least
_MIN_TRIPS_PER_SLOT trips in each slot before making a call, matching the
PRD's "~5 trips" framing (loosely - 5 total isn't enough to split
confidently across two time slots, so this uses a slightly lower per-slot
threshold intentionally, documented here rather than silently deviating).
"""

from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Trip, User

_MIN_TRIPS_PER_SLOT = 3
_NOON_HOUR = 12


def _pick_representative_trip(trips: list[Trip], winning_stop: str) -> Trip:
    """Among every trip matching the winning stop, prefers one that
    actually captured a mode+route_or_direction MTA/PATH candidates need
    to fetch live arrivals later (see recommendation_builder.
    _candidate_spec_for) - a plain "first match in query order" can just
    as easily land on an earlier trip logged before the user ever picked a
    specific route/direction tab, silently leaving home_route_or_direction
    null even when later trips for the same station did capture one. Falls
    back to the first match if none of them have one (nothing better to
    pick), same behavior as before for that case.
    """
    for trip in trips:
        if trip.origin_stop == winning_stop and trip.route_or_direction:
            return trip
    return next(t for t in trips if t.origin_stop == winning_stop)


def infer_home_and_office(db: Session, user_id) -> User:
    """Updates home_station/office_station (plus their _mode companions) if
    enough data exists. Does NOT touch home_office_confirmed - that's only
    set true by the user explicitly confirming (see routers/home_office.py),
    per the PRD's "confirmed once via a prompt" step. Re-running this after
    confirmation still updates the underlying inference (so it can be
    re-confirmed later if it changes), it just doesn't un-confirm anything
    by itself.

    home_mode/office_mode record which agency (Trip.mode, e.g. "mta",
    "njt_rail") the winning station code came from - a bare station code
    is ambiguous across agencies (MTA and NJT bus in particular can both
    use plain numeric-looking IDs), and anything that later wants to fetch
    live arrivals for the inferred station (e.g. the commute notification
    job) needs to know which API to call. home_route_or_direction/
    office_route_or_direction similarly record the specific route/
    direction viewed on the winning trip, if any - MTA/PATH need one to
    fetch arrivals, NJT rail/bus don't (see the User model's docstring).
    """
    user = db.get(User, user_id)
    trips = db.scalars(select(Trip).where(Trip.user_id == user_id)).all()

    morning_trips = [t for t in trips if t.start_time.hour < _NOON_HOUR]
    evening_trips = [t for t in trips if t.start_time.hour >= _NOON_HOUR]

    morning_stops = Counter(t.origin_stop for t in morning_trips)
    evening_stops = Counter(t.origin_stop for t in evening_trips)

    if sum(morning_stops.values()) >= _MIN_TRIPS_PER_SLOT:
        winning_stop = morning_stops.most_common(1)[0][0]
        winning_trip = _pick_representative_trip(morning_trips, winning_stop)
        user.home_station = winning_stop
        user.home_mode = winning_trip.mode
        user.home_route_or_direction = winning_trip.route_or_direction
    if sum(evening_stops.values()) >= _MIN_TRIPS_PER_SLOT:
        winning_stop = evening_stops.most_common(1)[0][0]
        winning_trip = _pick_representative_trip(evening_trips, winning_stop)
        user.office_station = winning_stop
        user.office_mode = winning_trip.mode
        user.office_route_or_direction = winning_trip.route_or_direction

    db.flush()
    return user


def infer_home_and_office_for_all_users(db: Session) -> int:
    """Returns the number of users processed. See recompute_all_preferences
    in preference_engine.py - same pattern, same nightly-job stand-in."""
    user_ids = db.scalars(select(User.id)).all()
    for user_id in user_ids:
        infer_home_and_office(db, user_id)
    db.commit()
    return len(user_ids)
