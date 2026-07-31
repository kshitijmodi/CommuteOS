"""Seeds a demo user with ~3 weeks of realistic-looking synthetic trip
history, so Phase 2 preference learning and Phase 3 recommendations have
something real to compute against and show during a demo, instead of empty
states. This is NOT real usage data - see OPEN_QUESTIONS.md for why (no
real 2-week usage history exists yet per the PRD's own Phase 3 cold-start
requirement).

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
# and PATH - matches the two agencies already live in the app.
_PRIMARY_STOP = ("mta", "R20N")  # Union Sq, N/Q/R/W northbound
_ALT_STOPS = [("mta", "631N"), ("path", "JSQ")]  # 14 St 4/5/6; PATH Journal Sq


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
        # "creature of habit, occasionally varies" pattern.
        mode, stop = (
            _PRIMARY_STOP if random.random() < 0.8 else random.choice(_ALT_STOPS)
        )

        # Morning commute around 8:00-8:30am, with natural jitter.
        start_time = day.replace(
            hour=8, minute=random.randint(0, 30), second=0, microsecond=0
        )

        db.add(
            Trip(
                user_id=user.id,
                start_time=start_time,
                mode=mode,
                origin_stop=stop,
            )
        )
        created += 1

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
