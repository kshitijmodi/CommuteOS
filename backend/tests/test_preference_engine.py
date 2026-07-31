from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models import Preference, Trip, User
from app.preference_engine import (
    DEFAULT_WALKING_TOLERANCE_M,
    recompute_all_preferences,
    recompute_preferences_for_user,
)


def _make_user(db_session, email="pref@example.com"):
    user = User(email=email, hashed_password=hash_password("hunter2"))
    db_session.add(user)
    db_session.flush()
    db_session.add(Preference(user_id=user.id))
    db_session.commit()
    return user


def _add_trip(db_session, user_id, origin_stop, days_ago=0):
    db_session.add(
        Trip(
            user_id=user_id,
            start_time=datetime.now(timezone.utc) - timedelta(days=days_ago),
            mode="mta",
            origin_stop=origin_stop,
        )
    )


def test_leaves_default_tolerance_with_too_few_trips(db_session):
    user = _make_user(db_session)
    for i in range(3):  # below the 5-trip minimum
        _add_trip(db_session, user.id, "R20N", days_ago=i)
    db_session.commit()

    preference = recompute_preferences_for_user(db_session, user.id)

    assert preference.walking_tolerance_m == DEFAULT_WALKING_TOLERANCE_M


def test_single_dominant_stop_lowers_tolerance(db_session):
    user = _make_user(db_session)
    for i in range(6):
        _add_trip(db_session, user.id, "R20N", days_ago=i)
    db_session.commit()

    preference = recompute_preferences_for_user(db_session, user.id)

    assert preference.walking_tolerance_m == 300.0


def test_many_distinct_stops_raises_tolerance(db_session):
    user = _make_user(db_session)
    stops = ["R20N", "R20S", "A31N", "A31S", "132N"]
    for i, stop in enumerate(stops):
        # visit each stop twice so it counts as "regularly used"
        _add_trip(db_session, user.id, stop, days_ago=i)
        _add_trip(db_session, user.id, stop, days_ago=i + 10)
    db_session.commit()

    preference = recompute_preferences_for_user(db_session, user.id)

    assert preference.walking_tolerance_m == 600.0


def test_transfer_aversion_score_is_never_touched(db_session):
    user = _make_user(db_session)
    preference = db_session.get(Preference, user.id)
    preference.transfer_aversion_score = 0.123
    db_session.commit()

    for i in range(6):
        _add_trip(db_session, user.id, "R20N", days_ago=i)
    db_session.commit()

    result = recompute_preferences_for_user(db_session, user.id)

    assert result.transfer_aversion_score == 0.123


def test_recompute_all_preferences_covers_every_user(db_session):
    user1 = _make_user(db_session, email="one@example.com")
    user2 = _make_user(db_session, email="two@example.com")
    for i in range(6):
        _add_trip(db_session, user1.id, "R20N", days_ago=i)
    db_session.commit()

    count = recompute_all_preferences(db_session)

    assert count == 2
    pref1 = db_session.get(Preference, user1.id)
    pref2 = db_session.get(Preference, user2.id)
    assert pref1.walking_tolerance_m == 300.0
    assert pref2.walking_tolerance_m == DEFAULT_WALKING_TOLERANCE_M
