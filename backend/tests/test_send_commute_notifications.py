from datetime import datetime, timedelta, timezone

import pytest

from app.core.security import hash_password
from app.jobs.send_commute_notifications import (
    send_notification_for_user,
    send_notifications_for_all_users,
)
from app.models import Preference, User
from app.transit.models import Arrival, ArrivalsResult


def _make_user(db_session, **kwargs):
    user = User(email=kwargs.pop("email", "notify@example.com"), hashed_password=hash_password("hunter2"), **kwargs)
    db_session.add(user)
    db_session.flush()
    db_session.add(Preference(user_id=user.id))
    db_session.commit()
    return user


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


@pytest.mark.asyncio
async def test_skips_unconfirmed_user(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=False,
        fcm_token="token123",
    )

    result = await send_notification_for_user(db_session, user)

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

    result = await send_notification_for_user(db_session, user)

    assert result is False
    assert mock_transit_and_push == []


@pytest.mark.asyncio
async def test_skips_mta_station_with_no_captured_route(db_session, mock_transit_and_push):
    user = _make_user(
        db_session,
        home_station="R20N",
        home_mode="mta",
        home_route_or_direction=None,  # never captured - see the module docstring
        home_office_confirmed=True,
        fcm_token="token123",
    )

    result = await send_notification_for_user(db_session, user)

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

    result = await send_notification_for_user(db_session, user)

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

    result = await send_notification_for_user(db_session, user)

    assert result is True


@pytest.mark.asyncio
async def test_send_notifications_for_all_users_counts_only_actual_sends(
    db_session, mock_transit_and_push
):
    _make_user(
        db_session,
        email="eligible@example.com",
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
        fcm_token="token123",
    )
    _make_user(
        db_session,
        email="not-confirmed@example.com",
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=False,
        fcm_token="token456",
    )
    _make_user(
        db_session,
        email="no-station@example.com",
        home_office_confirmed=True,
        fcm_token="token789",
    )

    count = await send_notifications_for_all_users(db_session)

    assert count == 1
