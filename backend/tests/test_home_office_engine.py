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


def _add_trip(
    db_session, user_id, origin_stop, hour, days_ago=0, mode="mta", route_or_direction=None
):
    db_session.add(
        Trip(
            user_id=user_id,
            start_time=(
                datetime.now(timezone.utc) - timedelta(days=days_ago)
            ).replace(hour=hour, minute=0, second=0, microsecond=0),
            mode=mode,
            origin_stop=origin_stop,
            route_or_direction=route_or_direction,
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


def test_records_mode_alongside_home_station(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "NP", hour=8, days_ago=i, mode="njt_rail")
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station == "NP"
    assert result.home_mode == "njt_rail"


def test_records_mode_alongside_office_station(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "1941", hour=18, days_ago=i, mode="njt_bus")
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.office_station == "1941"
    assert result.office_mode == "njt_bus"


def test_records_route_or_direction_when_present(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(
            db_session, user.id, "R20N", hour=8, days_ago=i, mode="mta", route_or_direction="N"
        )
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_route_or_direction == "N"


def test_route_or_direction_stays_null_when_never_logged(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "NP", hour=8, days_ago=i, mode="njt_rail")
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_route_or_direction is None


def test_home_and_office_modes_tracked_independently_across_agencies(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i, mode="mta")
        _add_trip(db_session, user.id, "NP", hour=18, days_ago=i, mode="njt_rail")
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_mode == "mta"
    assert result.office_mode == "njt_rail"


def test_prefers_a_trip_with_route_or_direction_over_an_earlier_routeless_one(db_session):
    # Regression test for a real bug: infer_home_and_office used to just
    # take the FIRST trip matching the winning stop in query order (via
    # next()), regardless of whether it had a route_or_direction. If a
    # user's earliest trip to their usual station happened before they
    # picked a specific route tab (or - as found via a demo/test seeding
    # mishap - some trips were logged without one at all), home_station
    # would resolve correctly but home_route_or_direction stayed null even
    # though later trips for the SAME station did capture one - silently
    # breaking MTA/PATH auto-recommendations, which can't fetch arrivals
    # without a route_or_direction (see recommendation_builder.
    # _candidate_spec_for).
    user = _make_user(db_session)
    _add_trip(db_session, user.id, "R20N", hour=8, days_ago=5, mode="mta")  # no route - earliest
    for i in range(4):
        _add_trip(
            db_session, user.id, "R20N", hour=8, days_ago=i, mode="mta", route_or_direction="N"
        )
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station == "R20N"
    assert result.home_route_or_direction == "N"


def test_falls_back_to_first_match_when_none_have_route_or_direction(db_session):
    user = _make_user(db_session)
    for i in range(4):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i, mode="mta")
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_station == "R20N"
    assert result.home_route_or_direction is None


def test_does_not_touch_confirmed_flag(db_session):
    user = _make_user(db_session)
    user.home_office_confirmed = True
    db_session.commit()

    for i in range(4):
        _add_trip(db_session, user.id, "R20N", hour=8, days_ago=i)
    db_session.commit()

    result = infer_home_and_office(db_session, user.id)

    assert result.home_office_confirmed is True
