"""Seeds a demo user with ~3 weeks of realistic-looking synthetic trip
history, so Phase 2 preference learning and Phase 3 recommendations have
something real to compute against and show during a demo, instead of empty
states. This is NOT real usage data - see OPEN_QUESTIONS.md for why (no
real 2-week usage history exists yet per the PRD's own Phase 3 cold-start
requirement).

Seeds BOTH morning (home-bound) and evening (office-bound) trips - the
home/office inference engine (see home_office_engine.py) needs at least 3
trips in each time slot before it can infer a station for that slot at
all. An earlier version of this script only seeded mornings, which meant
a demo account could get a home station but never an office one - and
without both, GET /recommendations/from-home-office (and the new
tradeoff-explaining comparison it feeds) has nothing to build a real
alternative from.

Usage: python -m app.jobs.seed_demo_trips [email]
Defaults to demo@commuteos.dev / demo-password-123 if no email given;
creates the user if it doesn't already exist.
"""

import random
import sys
from datetime import datetime, timedelta, timezone

from ..core.database import SessionLocal
from ..core.security import hash_password
from ..models import Preference, Trip, User

DEMO_EMAIL_DEFAULT = "demo@commuteos.dev"
DEMO_PASSWORD = "demo-password-123"

# A plausible commute: mostly one home station, occasionally a nearby
# alternate (models a real "usually X, sometimes Y" pattern), across MTA
# and PATH - matches the two agencies already live in the app. Each tuple
# is (mode, station, route_or_direction) - MTA/PATH candidates are
# silently dropped by recommendation_builder._candidate_spec_for without a
# real route_or_direction (it can't call their get_arrivals without one),
# so this must be a real value, not empty.
_HOME_PRIMARY_STOP = ("mta", "R20N", "N")  # Union Sq, N train northbound
_HOME_ALT_STOPS = [
    ("mta", "631N", "6"),  # 14 St, 6 train northbound
    ("path", "JSQ", "ToNY"),  # PATH Journal Sq, toward NY
]

# The evening/office-bound leg - a different real station/agency than the
# home leg, so home-vs-office genuinely reads as two distinct alternatives
# rather than the same station twice. NJT rail/PATH need no
# route_or_direction (see _candidate_spec_for) - left empty.
_OFFICE_PRIMARY_STOP = ("njt_rail", "NP", "")  # Newark Penn Station
_OFFICE_ALT_STOPS = [("path", "33", "")]  # PATH 33 St


def _get_or_create_demo_user(db, email: str) -> User:
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is not None:
        return user

    user = User(email=email, hashed_password=hash_password(DEMO_PASSWORD))
    db.add(user)
    db.flush()
    db.add(Preference(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


def _seed_trips(db, user: User, days: int = 21) -> int:
    created = 0
    for day_offset in range(days):
        day = datetime.now(timezone.utc) - timedelta(days=day_offset)
        if day.weekday() >= 5:  # skip weekends - a commuter's trips are weekday
            continue

        # ~80% usual station, ~20% one of the alternates - a realistic
        # "creature of habit, occasionally varies" pattern - applied
        # independently to each leg.
        morning_mode, morning_stop, morning_route = (
            _HOME_PRIMARY_STOP if random.random() < 0.8 else random.choice(_HOME_ALT_STOPS)
        )
        evening_mode, evening_stop, evening_route = (
            _OFFICE_PRIMARY_STOP if random.random() < 0.8 else random.choice(_OFFICE_ALT_STOPS)
        )

        # Morning commute around 8:00-8:30am, evening around 5:30-6:00pm,
        # with natural jitter - see home_office_engine.py's noon-cutoff
        # heuristic for why these need to land on opposite sides of noon.
        morning_time = day.replace(
            hour=8, minute=random.randint(0, 30), second=0, microsecond=0
        )
        evening_time = day.replace(
            hour=17, minute=random.randint(30, 59), second=0, microsecond=0
        )

        db.add(
            Trip(
                user_id=user.id,
                start_time=morning_time,
                mode=morning_mode,
                origin_stop=morning_stop,
                route_or_direction=morning_route or None,
            )
        )
        db.add(
            Trip(
                user_id=user.id,
                start_time=evening_time,
                mode=evening_mode,
                origin_stop=evening_stop,
                route_or_direction=evening_route or None,
            )
        )
        created += 2

    db.commit()
    return created


def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else DEMO_EMAIL_DEFAULT

    db = SessionLocal()
    try:
        user = _get_or_create_demo_user(db, email)
        count = _seed_trips(db, user)
        print(f"Seeded {count} trips for {email} (password: {DEMO_PASSWORD}).")
        print("Run `python -m app.jobs.recompute_preferences` next to learn from them.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
