from datetime import datetime, timedelta, timezone

import pytest

from app.transit.models import Arrival, ArrivalsResult


def _signup_and_login(client, email="commuteapi@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


@pytest.fixture(autouse=True)
def mock_transit_fetchers(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_mta_arrivals(stop_id, route_id):
        arrival_minutes = {"N": 5, "W": 10}.get(route_id, 5)
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=arrival_minutes))],
            is_live=True,
        )

    monkeypatch.setattr("app.recommendation_builder.mta.get_arrivals", fake_mta_arrivals)


def test_get_commute_recommendation_requires_auth(client):
    response = client.get("/commute/mta/R01")
    assert response.status_code == 401


def test_get_commute_recommendation_returns_real_ranked_candidates(client):
    token = _signup_and_login(client)

    response = client.get(
        "/commute/mta/R01", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "N"
    assert len(body["alternatives"]) == 1
    assert body["alternatives"][0]["label"] == "W"
    assert body["usual_route_or_direction"] is None
    assert body["differs_from_usual"] is False
    assert body["message"]


def test_get_commute_recommendation_404s_for_unknown_station(client):
    token = _signup_and_login(client, email="unknown@example.com")

    response = client.get(
        "/commute/mta/NOT_A_REAL_STOP", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 404
