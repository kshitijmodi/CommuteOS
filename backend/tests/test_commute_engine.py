from datetime import datetime, timedelta, timezone

import pytest

from app.commute_engine import candidates_for_station, recommend_for_station
from app.core.security import hash_password
from app.models import Trip, User
from app.transit.models import Arrival, ArrivalsResult


def _make_user(db_session, email="commute@example.com"):
    user = User(email=email, hashed_password=hash_password("hunter2"))
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user


def _at_hour(hour: int, days_ago: int = 0) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )


def test_candidates_for_station_returns_none_for_unknown_station():
    assert candidates_for_station("mta", "NOT_A_REAL_STOP_ID") is None


def test_candidates_for_station_returns_one_spec_per_mta_route():
    specs = candidates_for_station("mta", "R01")  # Astoria-Ditmars Blvd, routes N|W

    assert specs is not None
    assert {s.route_or_direction for s in specs} == {"N", "W"}
    assert all(s.stop_or_station == "R01" for s in specs)


def test_candidates_for_station_returns_both_path_directions():
    specs = candidates_for_station("path", "JSQ")

    assert specs is not None
    assert {s.route_or_direction for s in specs} == {"ToNY", "ToNJ"}


def test_candidates_for_station_returns_single_candidate_for_njt_rail():
    specs = candidates_for_station("njt_rail", "NP")  # Newark Penn Station

    assert specs is not None
    assert len(specs) == 1
    assert specs[0].route_or_direction == ""


@pytest.fixture(autouse=True)
def mock_transit_fetchers(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_mta_arrivals(stop_id, route_id):
        arrival_minutes = {"N": 5, "W": 10}.get(route_id, 5)
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=arrival_minutes))],
            is_live=True,
        )

    async def fake_path_arrivals(station_code, direction):
        return ArrivalsResult(
            arrivals=[Arrival(route_label="PATH", arrival_time=now + timedelta(minutes=8))],
            is_live=True,
        )

    monkeypatch.setattr("app.recommendation_builder.mta.get_arrivals", fake_mta_arrivals)
    monkeypatch.setattr("app.recommendation_builder.path.get_arrivals", fake_path_arrivals)


@pytest.mark.asyncio
async def test_recommend_for_station_returns_none_for_unknown_station(db_session):
    user = _make_user(db_session)

    result = await recommend_for_station(db_session, user.id, "mta", "NOT_REAL", reliability_pref=0.5)

    assert result is None


@pytest.mark.asyncio
async def test_recommend_for_station_ranks_real_candidates(db_session):
    user = _make_user(db_session)

    result = await recommend_for_station(db_session, user.id, "mta", "R01", reliability_pref=0.5)

    assert result is not None
    assert result.winner.label == "N"  # 5 min, sooner than W's 10 min
    assert len(result.alternatives) == 1
    assert result.alternatives[0].label == "W"


@pytest.mark.asyncio
async def test_recommend_for_station_has_no_usual_without_enough_history(db_session):
    user = _make_user(db_session)

    result = await recommend_for_station(db_session, user.id, "mta", "R01", reliability_pref=0.5)

    assert result.usual_route_or_direction is None
    assert result.differs_from_usual is False


@pytest.mark.asyncio
async def test_recommend_for_station_flags_when_winner_differs_from_usual(db_session):
    user = _make_user(db_session)
    # User's real history at this station/hour shows they usually take W -
    # but live data (see fixture) makes N the real winner right now.
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(datetime.now(timezone.utc).hour, days_ago=i),
                mode="mta",
                origin_stop="R01",
                route_or_direction="W",
            )
        )
    db_session.commit()

    result = await recommend_for_station(db_session, user.id, "mta", "R01", reliability_pref=0.5)

    assert result.usual_route_or_direction == "W"
    assert result.winner.label == "N"
    assert result.differs_from_usual is True


@pytest.mark.asyncio
async def test_recommend_for_station_does_not_flag_when_winner_matches_usual(db_session):
    user = _make_user(db_session)
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=_at_hour(datetime.now(timezone.utc).hour, days_ago=i),
                mode="mta",
                origin_stop="R01",
                route_or_direction="N",  # matches the real winner
            )
        )
    db_session.commit()

    result = await recommend_for_station(db_session, user.id, "mta", "R01", reliability_pref=0.5)

    assert result.usual_route_or_direction == "N"
    assert result.differs_from_usual is False
