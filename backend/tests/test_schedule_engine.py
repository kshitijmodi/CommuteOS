from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.models import Trip, User
from app.schedule_engine import (
    DisruptionSeverity,
    assess_candidate,
    classify_disruption,
    is_within_notification_window,
    usual_departure_hour_for,
)


def _make_user(db_session, email="schedule@example.com"):
    user = User(email=email, hashed_password=hash_password("hunter2"))
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user


def _at_hour(hour: int, days_ago: int = 0) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def test_usual_departure_hour_requires_minimum_samples(db_session):
    user = _make_user(db_session)
    for i in range(2):  # below the minimum of 3
        db_session.add(
            Trip(user_id=user.id, start_time=_at_hour(8, days_ago=i), mode="mta", origin_stop="R20N")
        )
    db_session.commit()

    assert usual_departure_hour_for(db_session, user.id, is_morning=True) is None


def test_usual_departure_hour_picks_most_common_morning_hour(db_session):
    user = _make_user(db_session)
    hours = [8, 8, 9]
    for i, hour in enumerate(hours):
        db_session.add(
            Trip(user_id=user.id, start_time=_at_hour(hour, days_ago=i), mode="mta", origin_stop="R20N")
        )
    db_session.commit()

    assert usual_departure_hour_for(db_session, user.id, is_morning=True) == 8


def test_usual_departure_hour_ignores_evening_trips_for_morning_query(db_session):
    user = _make_user(db_session)
    for i in range(3):
        db_session.add(
            Trip(user_id=user.id, start_time=_at_hour(18, days_ago=i), mode="mta", origin_stop="R20S")
        )
    db_session.commit()

    assert usual_departure_hour_for(db_session, user.id, is_morning=True) is None
    assert usual_departure_hour_for(db_session, user.id, is_morning=False) == 18


def test_is_within_notification_window_one_hour_before_usual():
    assert is_within_notification_window(now_hour=7, usual_departure_hour=8) is True
    assert is_within_notification_window(now_hour=8, usual_departure_hour=8) is False
    assert is_within_notification_window(now_hour=6, usual_departure_hour=8) is False


def test_is_within_notification_window_wraps_around_midnight():
    assert is_within_notification_window(now_hour=23, usual_departure_hour=0) is True


def test_classify_disruption_on_time_within_tolerance():
    typical_minute = 8 * 60 + 10  # 8:10
    live = datetime(2026, 1, 1, 8, 12, tzinfo=timezone.utc)  # 2 min later - within tolerance

    result = classify_disruption(live, typical_minute)

    assert result.severity == DisruptionSeverity.ON_TIME


def test_classify_disruption_delayed_beyond_tolerance():
    typical_minute = 8 * 60 + 10  # 8:10
    live = datetime(2026, 1, 1, 8, 25, tzinfo=timezone.utc)  # 15 min later

    result = classify_disruption(live, typical_minute)

    assert result.severity == DisruptionSeverity.DELAYED
    assert result.delay_minutes == 15.0


def test_classify_disruption_no_baseline_degrades_to_on_time_not_a_guess():
    live = datetime(2026, 1, 1, 8, 25, tzinfo=timezone.utc)

    result = classify_disruption(live, None)

    assert result.severity == DisruptionSeverity.ON_TIME
    assert result.delay_minutes is None


def test_assess_candidate_no_live_data():
    result = assess_candidate(None, None, "R20N", hour=8, live_predicted_arrival=None)

    assert result.severity == DisruptionSeverity.NO_LIVE_DATA
    assert result.delay_minutes is None


def test_assess_candidate_uses_real_typical_arrival_baseline(db_session):
    user = _make_user(db_session)
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=_at_hour(8, days_ago=i).replace(minute=10),
            )
        )
    db_session.commit()

    live_predicted_arrival = datetime.now(timezone.utc).replace(hour=8, minute=25, second=0, microsecond=0)

    result = assess_candidate(db_session, user.id, "R20N", hour=8, live_predicted_arrival=live_predicted_arrival)

    assert result.severity == DisruptionSeverity.DELAYED
    assert result.delay_minutes == 15.0
