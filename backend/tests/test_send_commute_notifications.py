from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.jobs.send_commute_notifications import (
    send_notification_for_user,
    send_notifications_for_all_users,
)
from app.models import Preference, Trip, User
from app.transit.models import Arrival, ArrivalsResult


def _make_user(db_session, **kwargs):
    user = User(email=kwargs.pop("email", "notify@example.com"), hashed_password=hash_password("hunter2"), **kwargs)
    db_session.add(user)
    db_session.flush()
    db_session.add(Preference(user_id=user.id))
    db_session.commit()
    return user


def _add_morning_trips(db_session, user_id, origin_stop, hour, mode="njt_rail", days_ago_start=1):
    """Gives a user enough morning-trip history for
    schedule_engine.usual_departure_hour_for to resolve a real hour -
    without this, send_notification_for_user always returns False before
    ever reaching the live-fetch/push logic these tests actually exercise.
    """
    for i in range(days_ago_start, days_ago_start + 3):
        db_session.add(
            Trip(
                user_id=user_id,
                start_time=(datetime.now(timezone.utc) - timedelta(days=i)).replace(
                    hour=hour, minute=0, second=0, microsecond=0
                ),
                mode=mode,
                origin_stop=origin_stop,
            )
        )
    db_session.commit()


@pytest.fixture(autouse=True)
def mock_transit_and_push(monkeypatch):
    now = datetime.now(timezone.utc)
    sent = []

    async def fake_mta_arrivals(stop_id, route_id):
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=8))],
            is_live=True,
        )

    async def fake_njt_rail_arrivals(station_code):
        return ArrivalsResult(
            arrivals=[Arrival(route_label="NEC", arrival_time=now + timedelta(minutes=12))],
            is_live=True,
        )

    def fake_send_push(fcm_token, title, body):
        sent.append((fcm_token, title, body))

    monkeypatch.setattr("app.recommendation_builder.mta.get_arrivals", fake_mta_arrivals)
    monkeypatch.setattr("app.recommendation_builder.njt_rail.get_arrivals", fake_njt_rail_arrivals)
    monkeypatch.setattr("app.jobs.send_commute_notifications.send_push", fake_send_push)
    return sent


# A fixed "now" at 7am UTC - _add_morning_trips defaults to 8am departures,
# so usual_departure_hour_for resolves to 8, and 7am is exactly one
# _LEAD_HOURS before it (see schedule_engine.is_within_notification_window).
_NOW_WITHIN_WINDOW = datetime.now(timezone.utc).replace(
    hour=7, minute=0, second=0, microsecond=0
)


@pytest.mark.asyncio
async def test_skips_unconfirmed_user(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=False,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_skips_user_with_no_push_token(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token=None,
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_skips_mta_station_with_no_captured_route(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="R20N",
        home_mode="mta",
        home_route_or_direction=None,  # never captured - see recommendation_builder's docstring
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "R20N", hour=8, mode="mta")

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_skips_a_user_with_no_morning_trip_history(db_session, mock_transit_and_push):
    """usual_departure_hour_for needs 3+ morning trips - a user with none
    yet has no learned departure hour, so nothing can ever be "ahead of"
    it. Distinct from the old fixed-time behavior, where this user would
    have been notified anyway at the one global fixed time.
    """
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
    )

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_skips_when_now_is_outside_the_users_notification_window(
    db_session, mock_transit_and_push
):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)  # usual hour = 8, window = 7

    now_outside_window = _NOW_WITHIN_WINDOW.replace(hour=14)
    result = await send_notification_for_user(db_session, user, now_outside_window)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_skips_a_user_already_notified_today(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
        last_commute_notification_date=_NOW_WITHIN_WINDOW.date(),
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_sends_notification_for_njt_rail_home_station(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is True
    assert len(mock_transit_and_push) == 1
    assert mock_transit_and_push[0][0] == "token123"


@pytest.mark.asyncio
async def test_sends_notification_for_mta_station_with_captured_route(
    db_session, mock_transit_and_push
):
    user = _make_user(
        db_session,
        home_station="R20N",
        home_mode="mta",
        home_route_or_direction="N",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "R20N", hour=8, mode="mta")

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is True


@pytest.mark.asyncio
async def test_a_successful_send_marks_last_commute_notification_date(
    db_session, mock_transit_and_push
):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)

    await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert user.last_commute_notification_date == _NOW_WITHIN_WINDOW.date()


@pytest.mark.asyncio
async def test_no_live_data_falls_back_to_a_real_substitute(db_session, monkeypatch):
    """When the user's usual (home) candidate has no live arrivals at
    all, Schedule AI delegates to rank_routes across every real candidate
    rather than sending an empty/broken notification - see
    schedule_engine.py's module docstring on delegation.
    """
    now = datetime.now(timezone.utc)
    sent = []

    async def empty_njt_rail(station_code):
        return ArrivalsResult(arrivals=[], is_live=True)

    async def fake_mta_arrivals(stop_id, route_id):
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=8))],
            is_live=True,
        )

    def fake_send_push(fcm_token, title, body):
        sent.append((fcm_token, title, body))

    monkeypatch.setattr("app.recommendation_builder.njt_rail.get_arrivals", empty_njt_rail)
    monkeypatch.setattr("app.recommendation_builder.mta.get_arrivals", fake_mta_arrivals)
    monkeypatch.setattr("app.jobs.send_commute_notifications.send_push", fake_send_push)

    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        office_station="R20N",
        office_mode="mta",
        office_route_or_direction="N",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, user.id, "NP", hour=8)

    result = await send_notification_for_user(db_session, user, _NOW_WITHIN_WINDOW)

    assert result is True
    assert len(sent) == 1
    assert "N" in sent[0][2] or "isn't showing live data" in sent[0][2]


@pytest.mark.asyncio
async def test_send_notifications_for_all_users_counts_only_actual_sends(
    db_session, mock_transit_and_push
):
    eligible = _make_user(
        db_session,
        email="eligible@example.com",
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _add_morning_trips(db_session, eligible.id, "NP", hour=8)

    not_confirmed = _make_user(
        db_session,
        email="not-confirmed@example.com",
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=False,
        fcm_token="token456",
    )
    _add_morning_trips(db_session, not_confirmed.id, "NP", hour=8)

    _make_user(
        db_session,
        email="no-station@example.com",
        home_office_confirmed=True,
        fcm_token="token789",
    )

    count = await send_notifications_for_all_users(db_session, now=_NOW_WITHIN_WINDOW)

    assert count == 1
