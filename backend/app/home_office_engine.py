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


def infer_home_and_office(db: Session, user_id) -> User:
    """Updates home_station/office_station if enough data exists. Does NOT
    touch home_office_confirmed - that's only set true by the user
    explicitly confirming (see routers/home_office.py), per the PRD's
    "confirmed once via a prompt" step. Re-running this after confirmation
    still updates the underlying inference (so it can be re-confirmed
    later if it changes), it just doesn't un-confirm anything by itself.
    """
    user = db.get(User, user_id)
    trips = db.scalars(select(Trip).where(Trip.user_id == user_id)).all()

    morning_stops = Counter(
        t.origin_stop for t in trips if t.start_time.hour < _NOON_HOUR
    )
    evening_stops = Counter(
        t.origin_stop for t in trips if t.start_time.hour >= _NOON_HOUR
    )

    if sum(morning_stops.values()) >= _MIN_TRIPS_PER_SLOT:
        user.home_station = morning_stops.most_common(1)[0][0]
    if sum(evening_stops.values()) >= _MIN_TRIPS_PER_SLOT:
        user.office_station = evening_stops.most_common(1)[0][0]

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
