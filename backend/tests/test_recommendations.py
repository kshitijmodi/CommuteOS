from datetime import datetime, timedelta, timezone

import pytest

from app.transit.models import Arrival, ArrivalsResult


def _signup_and_login(client, email="rec@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


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

    monkeypatch.setattr(
        "app.routers.recommendations.mta.get_arrivals", fake_mta_arrivals
    )
    monkeypatch.setattr(
        "app.routers.recommendations.path.get_arrivals", fake_path_arrivals
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
