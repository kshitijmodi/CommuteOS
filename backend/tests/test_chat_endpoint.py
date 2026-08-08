from datetime import datetime, timedelta, timezone

import pytest

from app.transit.models import Arrival, ArrivalsResult


def _signup_and_login(client, email="chatendpoint@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


@pytest.fixture(autouse=True)
def no_llm_key(monkeypatch):
    monkeypatch.setattr("app.chat_ai.settings.groq_api_key", None)


@pytest.fixture(autouse=True)
def mock_transit_fetchers(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_mta(stop_id, route_id):
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=5))],
            is_live=True,
        )

    monkeypatch.setattr("app.chat_ai.mta.get_arrivals", fake_mta)
    monkeypatch.setattr("app.recommendation_builder.mta.get_arrivals", fake_mta)


def test_chat_requires_no_auth(client):
    response = client.post("/chat", json={"question": "how much does a fare cost?"})
    assert response.status_code == 200


def test_chat_refuses_out_of_scope_question(client):
    response = client.post("/chat", json={"question": "what's the weather like"})

    assert response.status_code == 200
    body = response.json()
    assert "don't have that information" in body["answer"]
    assert body["station_name"] is None


def test_chat_asks_for_clarification_on_no_match(client):
    response = client.post(
        "/chat", json={"question": "tell me about nowhere realzzz"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["station_name"] is None


def test_chat_works_with_a_real_valid_token(client):
    token = _signup_and_login(client)

    response = client.post(
        "/chat",
        json={"question": "what do I usually take from Astoria-Ditmars Blvd"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["station_name"] == "Astoria-Ditmars Blvd"


def test_chat_treats_an_invalid_token_as_anonymous_not_an_error(client):
    response = client.post(
        "/chat",
        json={"question": "what's the next PATH train from Grove Street"},
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 200


def test_chat_works_with_no_authorization_header_at_all(client):
    response = client.post(
        "/chat", json={"question": "what's the next PATH train from Grove Street"}
    )

    assert response.status_code == 200


def test_chat_finds_a_real_nearest_station_with_real_coordinates(client):
    response = client.post(
        "/chat",
        json={
            "question": "what is the nearest path station to me?",
            "lat": 40.7318097,
            "lng": -74.0628655,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["station_name"] == "Journal Square"
    assert body["agency"] == "path"


def test_chat_refuses_nearest_question_without_coordinates(client):
    response = client.post(
        "/chat", json={"question": "what is the nearest path station to me?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["station_name"] is None
    assert "location" in body["answer"].lower()
