"""Recomputes a user's Preferences row from their Trip history.

Per the PRD, this is a nightly batch job, not live inference - deliberately
simple, deterministic, and debuggable rather than a model that's hard to
explain. Call `recompute_preferences_for_user` for one user (used by the
scheduled job and by tests); `recompute_all_preferences` sweeps every user.

What's actually computable today vs. what the PRD envisions long-term:
- walking_tolerance_m: the PRD's ideal signal is "distance the user accepts
  before choosing a farther/less-crowded station over their nearest one."
  We don't have station-distance data or a "nearest station" concept wired
  up yet, so this uses a coarser proxy for now: how many distinct origin
  stops a user visits regularly (a user who always uses one station has an
  unknown-but-presumably-low tolerance; a user spreading trips across many
  nearby stations is more willing to walk further for a better option).
  This is intentionally conservative - it nudges the default rather than
  replacing it outright, and is documented here so nobody mistakes the
  proxy for the PRD's real target metric.
- transfer_aversion_score: the PRD's signal requires knowing when a user
  was shown both a direct and a transfer route and picked one - that
  comparison doesn't exist anywhere in our data model yet (no route
  planning, no alternative-route logging). Left at its schema default
  (0.5, neutral) until that data exists. Computing a fake number here
  would be worse than an honest "not yet knowable."
"""

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Preference, Trip, User

DEFAULT_WALKING_TOLERANCE_M = 400.0
_MIN_TRIPS_FOR_WALKING_TOLERANCE = 5  # PRD: "over ~5 trips"


def recompute_preferences_for_user(db: Session, user_id) -> Preference:
    trips = db.scalars(
        select(Trip).where(Trip.user_id == user_id)
    ).all()

    preference = db.get(Preference, user_id)
    if preference is None:
        preference = Preference(user_id=user_id)
        db.add(preference)

    if len(trips) >= _MIN_TRIPS_FOR_WALKING_TOLERANCE:
        preference.walking_tolerance_m = _estimate_walking_tolerance(trips)

    # transfer_aversion_score intentionally left untouched - see module
    # docstring. Not computed from data that doesn't exist yet.

    preference.updated_at = datetime.now(timezone.utc)
    db.flush()
    return preference


def recompute_all_preferences(db: Session) -> int:
    """Returns the number of users whose preferences were recomputed."""
    user_ids = db.scalars(select(User.id)).all()
    for user_id in user_ids:
        recompute_preferences_for_user(db, user_id)
    db.commit()
    return len(user_ids)


def _estimate_walking_tolerance(trips: list[Trip]) -> float:
    """Coarse proxy described in the module docstring: more distinct
    regularly-used origin stops -> nudge tolerance up; a single dominant
    stop -> nudge down. Bounded so a handful of noisy trips can't send this
    to an extreme value.
    """
    stop_counts = Counter(trip.origin_stop for trip in trips)
    distinct_stops_used = len(
        [stop for stop, count in stop_counts.items() if count >= 2]
    )

    if distinct_stops_used <= 1:
        return 300.0  # sticks to one station - assume lower tolerance
    if distinct_stops_used >= 4:
        return 600.0  # spreads across many stations - assume higher tolerance
    return DEFAULT_WALKING_TOLERANCE_M
