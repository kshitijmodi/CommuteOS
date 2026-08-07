import pytest


@pytest.fixture(autouse=True)
def no_llm_key(monkeypatch):
    monkeypatch.setattr("app.chat_ai.settings.groq_api_key", None)


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
