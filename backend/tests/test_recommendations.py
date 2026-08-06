from datetime import datetime, timedelta, timezone

import pytest

from app.models import User
from app.transit.models import Arrival, ArrivalsResult


def _signup_and_login(client, email="rec@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


def _set_home_office(db_session, email, **kwargs):
    user = db_session.query(User).filter(User.email == email).one()
    for key, value in kwargs.items():
        setattr(user, key, value)
    db_session.commit()


@pytest.fixture(autouse=True)
def mock_transit_fetchers(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_mta_arrivals(stop_id, route_id):
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=10))],
            is_live=True,
        )

    async def fake_path_arrivals(station_code, direction):
        return ArrivalsResult(
            arrivals=[Arrival(route_label="PATH", arrival_time=now + timedelta(minutes=15))],
            is_live=True,
        )

    async def fake_njt_rail_arrivals(station_code):
        return ArrivalsResult(
            arrivals=[Arrival(route_label="NEC", arrival_time=now + timedelta(minutes=20))],
            is_live=True,
        )

    async def fake_njt_bus_arrivals(stop_id):
        return ArrivalsResult(
            arrivals=[Arrival(route_label="163", arrival_time=now + timedelta(minutes=25))],
            is_live=True,
        )

    async def fake_lirr_arrivals(station_code):
        return ArrivalsResult(
            arrivals=[
                Arrival(route_label="Babylon Branch", arrival_time=now + timedelta(minutes=30))
            ],
            is_live=True,
        )

    monkeypatch.setattr(
        "app.recommendation_builder.mta.get_arrivals", fake_mta_arrivals
    )
    monkeypatch.setattr(
        "app.recommendation_builder.path.get_arrivals", fake_path_arrivals
    )
    monkeypatch.setattr(
        "app.recommendation_builder.njt_bus.get_arrivals", fake_njt_bus_arrivals
    )
    monkeypatch.setattr(
        "app.recommendation_builder.njt_rail.get_arrivals", fake_njt_rail_arrivals
    )
    monkeypatch.setattr(
        "app.recommendation_builder.lirr.get_arrivals", fake_lirr_arrivals
    )


def test_recommendation_requires_auth(client):
    response = client.post("/recommendations", json={"candidates": []})
    assert response.status_code == 401


def test_recommendation_rejects_empty_candidates(client):
    token = _signup_and_login(client)
    response = client.post(
        "/recommendations",
        json={"candidates": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 400


def test_recommendation_picks_soonest_candidate(client):
    token = _signup_and_login(client, email="soonest@example.com")

    response = client.post(
        "/recommendations",
        json={
            "candidates": [
                {
                    "agency": "mta",
                    "label": "N train",
                    "stop_or_station": "R20N",
                    "route_or_direction": "N",
                },
                {
                    "agency": "path",
                    "label": "PATH",
                    "stop_or_station": "JSQ",
                    "route_or_direction": "ToNY",
                },
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    # MTA candidate arrives at +10min, PATH at +15min in the mock - MTA wins.
    assert body["mode"] == "mta"
    assert body["label"] == "N train"
    assert body["confidence"] == 0.9
    assert len(body["message"]) > 0
    assert body["trip_id"]
    # The loser (PATH) should come back as an alternative, not just be
    # discarded - the whole point of comparing 2+ real candidates is being
    # able to show/explain the tradeoff, not just the winner in isolation.
    assert len(body["alternatives"]) == 1
    assert body["alternatives"][0]["mode"] == "path"
    assert body["alternatives"][0]["label"] == "PATH"


def test_recommendation_has_no_alternatives_for_a_single_candidate(client):
    token = _signup_and_login(client, email="onecandidate@example.com")

    response = client.post(
        "/recommendations",
        json={
            "candidates": [
                {
                    "agency": "mta",
                    "label": "N train",
                    "stop_or_station": "R20N",
                    "route_or_direction": "N",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["alternatives"] == []


def test_recommendation_supports_njt_rail_candidate(client):
    token = _signup_and_login(client, email="njt@example.com")

    response = client.post(
        "/recommendations",
        json={
            "candidates": [
                {
                    "agency": "njt_rail",
                    "label": "NJT from Newark Penn",
                    "stop_or_station": "NP",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "njt_rail"
    assert body["label"] == "NJT from Newark Penn"


def test_recommendation_supports_njt_bus_candidate(client):
    token = _signup_and_login(client, email="njtbus@example.com")

    response = client.post(
        "/recommendations",
        json={
            "candidates": [
                {
                    "agency": "njt_bus",
                    "label": "163 bus",
                    "stop_or_station": "1941",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "njt_bus"
    assert body["label"] == "163 bus"


def test_recommendation_supports_lirr_candidate(client):
    token = _signup_and_login(client, email="lirr@example.com")

    response = client.post(
        "/recommendations",
        json={
            "candidates": [
                {
                    "agency": "lirr",
                    "label": "Jamaica",
                    "stop_or_station": "JAM",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "lirr"
    assert body["label"] == "Jamaica"


def test_recommendation_logs_a_trip(client, db_session):
    from app.models import Trip

    token = _signup_and_login(client, email="logtrip@example.com")

    client.post(
        "/recommendations",
        json={
            "candidates": [
                {
                    "agency": "mta",
                    "label": "N train",
                    "stop_or_station": "R20N",
                    "route_or_direction": "N",
                }
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    trips = db_session.query(Trip).all()
    assert len(trips) == 1
    assert trips[0].mode == "mta"
    assert trips[0].predicted_arrival is not None


def test_from_home_office_requires_auth(client):
    response = client.get("/recommendations/from-home-office")
    assert response.status_code == 401


def test_from_home_office_404s_when_not_confirmed(client, db_session):
    email = "unconfirmed@example.com"
    token = _signup_and_login(client, email=email)
    _set_home_office(
        db_session,
        email,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=False,
    )

    response = client.get(
        "/recommendations/from-home-office",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_from_home_office_404s_when_mta_route_never_captured(client, db_session):
    email = "norouteyet@example.com"
    token = _signup_and_login(client, email=email)
    _set_home_office(
        db_session,
        email,
        home_station="R20N",
        home_mode="mta",
        home_route_or_direction=None,
        home_office_confirmed=True,
    )

    response = client.get(
        "/recommendations/from-home-office",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


def test_from_home_office_picks_soonest_of_home_and_office(client, db_session):
    email = "homeoffice@example.com"
    token = _signup_and_login(client, email=email)
    _set_home_office(
        db_session,
        email,
        home_station="R20N",
        home_mode="mta",
        home_route_or_direction="N",
        office_station="JSQ",
        office_mode="path",
        office_route_or_direction="ToNY",
        home_office_confirmed=True,
    )

    response = client.get(
        "/recommendations/from-home-office",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    # MTA (home) arrives at +10min, PATH (office) at +15min in the mock.
    assert body["mode"] == "mta"
    assert body["label"] == "R20N"
    assert body["trip_id"]
    assert len(body["alternatives"]) == 1
    assert body["alternatives"][0]["mode"] == "path"


def test_from_home_office_logs_a_trip(client, db_session):
    from app.models import Trip

    email = "homeofficetrip@example.com"
    token = _signup_and_login(client, email=email)
    _set_home_office(
        db_session,
        email,
        home_station="NP",
        home_mode="njt_rail",
        home_office_confirmed=True,
    )

    client.get(
        "/recommendations/from-home-office",
        headers={"Authorization": f"Bearer {token}"},
    )

    trips = db_session.query(Trip).all()
    assert len(trips) == 1
    assert trips[0].mode == "njt_rail"
