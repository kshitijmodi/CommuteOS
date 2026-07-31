from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.home_office_engine import (
    infer_home_and_office,
    infer_home_and_office_for_all_users,
)
from app.models import Preference, Trip, User


def _make_user(db_session, email="homeoffice@example.com"):
    user = User(email=email, hashed_password=hash_password("hunter2"))
    db_session.add(user)
    db_session.flush()
    db_session.add(Preference(user_id=user.id))
    db_session.commit()
    return user


def _add_trip(db_session, user_id, origin_stop, hour, days_ago=0):
    db_session.add(
        Trip(
            user_id=user_id,
            start_time=(
                datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour, minute=0, second=0, microsecond=0),
            mode="mta",
            origin_stop=origin_stop,
        )
    )


def test_no_inference_with_too_few_trips(db_session):
    user = _make_user(db_session)
    _add_trip(db_session, user.id, "R20N", hour=8, days_ago=0)
    _add_trip(db_session, user.id, "R20N", hour=8, days_ago=1)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station is None
    assert result.office_station is None


def test_infers_home_from_morning_trips(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station == "R20N"


def test_infers_office_from_evening_trips(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "A31S", hour=18, days_ago=i)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.office_station == "A31S"


def test_infers_both_independently(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i)
        _add_trip(db_session, user.id, "A31S", hour=18, days_ago=i)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station == "R20N"
    assert result.office_station == "A31S"


def test_picks_most_common_stop_when_multiple_exist(db_session):
    user = _make_user(db_session)
    for i in range(5):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i)
    for i in range(2):
        _add_trip(db_session, user.id, "A31N", hour=8, days_ago=i + 10)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station == "R20N"


def test_infer_for_all_users_covers_everyone(db_session):
    user1 = _make_user(db_session, email="all1@example.com")
    user2 = _make_user(db_session, email="all2@example.com")
    for i in range(4):
        _add_trip(db_session, user1.id, "R20N", hour=8, days_ago=i)
    db_session.commit()

    count = infer_home_and_office_for_all_users(db_session)

    assert count == 2
    assert db_session.get(User, user1.id).home_station == "R20N"
    assert db_session.get(User, user2.id).home_station is None


def test_does_not_touch_confirmed_flag(db_session):
    user = _make_user(db_session)
    user.home_office_confirmed = True
    db_session.commit()

    for i in range(4):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_office_confirmed is True
