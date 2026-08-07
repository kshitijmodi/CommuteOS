from datetime import datetime, timedelta, timezone

from app.behavior_engine import (
    direction_choices_for_user,
    feed_accuracy_for_user,
    predict_direction,
    timing_buffers_for_user,
)
from app.core.security import hash_password
from app.models import Trip, User


def _make_user(db_session, email="behavior@example.com"):
    user = User(email=email, hashed_password=hash_password("hunter2"))
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user


def _at_hour(hour: int, days_ago: int = 0) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def test_feed_accuracy_requires_minimum_samples(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    for i in range(2):  # below the minimum of 3
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=now,
                actual_arrival=now + timedelta(minutes=2),
            )
        )
    db_session.commit()

    assert feed_accuracy_for_user(db_session, user.id) == []


def test_feed_accuracy_averages_error_once_enough_samples(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    errors = [1, 3, 5]  # minutes
    for i, error in enumerate(errors):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=now,
                actual_arrival=now + timedelta(minutes=error),
            )
        )
    db_session.commit()

    results = feed_accuracy_for_user(db_session, user.id)

    assert len(results) == 1
    result = results[0]
    assert result.mode == "mta"
    assert result.origin_stop == "R20N"
    assert result.sample_count == 3
    assert result.average_error_minutes == 3.0


def test_feed_accuracy_separates_by_time_slot(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),  # morning slot
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=now,
                actual_arrival=now + timedelta(minutes=2),
            )
        )
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(18, days_ago=i),  # evening slot
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=now,
                actual_arrival=now + timedelta(minutes=8),
            )
        )
    db_session.commit()

    results = feed_accuracy_for_user(db_session, user.id)

    assert len(results) == 2
    by_slot = {r.time_slot: r for r in results}
    assert by_slot[8 // 3].average_error_minutes == 2.0
    assert by_slot[18 // 3].average_error_minutes == 8.0


def test_direction_choice_picks_most_common_and_confidence(db_session):
    user = _make_user(db_session)
    routes = ["N", "N", "N", "R"]
    for i, route in enumerate(routes):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="JSQ",
                route_or_direction=route,
            )
        )
    db_session.commit()

    results = direction_choices_for_user(db_session, user.id)

    assert len(results) == 1
    result = results[0]
    assert result.most_common_route_or_direction == "N"
    assert result.sample_count == 4
    assert result.confidence == 0.75


def test_direction_choice_ignores_trips_without_route_or_direction(db_session):
    user = _make_user(db_session)
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="JSQ",
                route_or_direction=None,
            )
        )
    db_session.commit()

    assert direction_choices_for_user(db_session, user.id) == []


def test_predict_direction_returns_none_without_enough_history(db_session):
    user = _make_user(db_session)

    assert predict_direction(db_session, user.id, "JSQ", hour=8) is None


def test_predict_direction_matches_station_and_hour_slot(db_session):
    user = _make_user(db_session)
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="JSQ",
                route_or_direction="N",
            )
        )
    db_session.commit()

    result = predict_direction(db_session, user.id, "JSQ", hour=6)  # same 3-hour slot (6-8)

    assert result is not None
    assert result.most_common_route_or_direction == "N"

    assert predict_direction(db_session, user.id, "JSQ", hour=20) is None
    assert predict_direction(db_session, user.id, "33rd", hour=8) is None


def test_timing_buffer_averages_minutes_before_predicted_arrival(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    buffers = [5, 7, 9]  # minutes before predicted arrival
    for i, buffer_minutes in enumerate(buffers):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=now,
                left_at=now - timedelta(minutes=buffer_minutes),
            )
        )
    db_session.commit()

    results = timing_buffers_for_user(db_session, user.id)

    assert len(results) == 1
    assert results[0].sample_count == 3
    assert results[0].average_buffer_minutes == 7.0


def test_timing_buffer_ignores_trips_without_left_at(db_session):
    user = _make_user(db_session)
    now = datetime.now(timezone.utc)
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(8, days_ago=i),
                mode="mta",
                origin_stop="R20N",
                predicted_arrival=now,
                left_at=None,
            )
        )
    db_session.commit()

    assert timing_buffers_for_user(db_session, user.id) == []
