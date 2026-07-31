from datetime import datetime, timezone


def _signup_and_login(client, email="prefapi@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


def test_read_my_preferences_returns_defaults_for_new_user(client):
    token = _signup_and_login(client)

    response = client.get(
        "/preferences/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["walking_tolerance_m"] == 400.0
    assert body["transfer_aversion_score"] == 0.5
    assert body["reliability_pref"] == 0.5


def test_read_my_preferences_requires_auth(client):
    response = client.get("/preferences/me")
    assert response.status_code == 401


def test_recompute_updates_walking_tolerance_after_enough_trips(client):
    token = _signup_and_login(client, email="recompute@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for _ in range(6):
        client.post(
            "/trips",
            json={
                "start_time": datetime.now(timezone.utc).isoformat(),
                "mode": "mta",
                "origin_stop": "R20N",
            },
            headers=headers,
        )

    response = client.post("/preferences/me/recompute", headers=headers)

    assert response.status_code == 200
    assert response.json()["walking_tolerance_m"] == 300.0
