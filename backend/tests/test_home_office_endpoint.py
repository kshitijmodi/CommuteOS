from datetime import datetime, timedelta, timezone


def _signup_and_login(client, email="homeofficeapi@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


def test_read_starts_with_nothing_inferred(client):
    token = _signup_and_login(client)

    response = client.get(
        "/home-office/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["home_station"] is None
    assert body["office_station"] is None
    assert body["confirmed"] is False


def test_read_requires_auth(client):
    response = client.get("/home-office/me")
    assert response.status_code == 401


def test_infer_updates_home_station_after_enough_trips(client):
    token = _signup_and_login(client, email="infer@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(4):
        start = (datetime.now(timezone.utc) - timedelta(days=i)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        client.post(
            "/trips",
            json={
                "start_time": start.isoformat(),
                "mode": "mta",
                "origin_stop": "R20N",
            },
            headers=headers,
        )

    response = client.post("/home-office/me/infer", headers=headers)

    assert response.status_code == 200
    assert response.json()["home_station"] == "R20N"


def test_infer_also_returns_which_agency_the_home_station_belongs_to(client):
    # Real gap fixed 2026-08-12: home_mode/office_mode were already tracked
    # on User but never exposed here - a bare station code alone is
    # ambiguous across agencies, so nothing that needs to resolve the code
    # to a real station (e.g. background geofencing) could use this
    # endpoint before this field existed.
    token = _signup_and_login(client, email="infermode@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for i in range(4):
        start = (datetime.now(timezone.utc) - timedelta(days=i)).replace(
            hour=8, minute=0, second=0, microsecond=0
        )
        client.post(
            "/trips",
            json={
                "start_time": start.isoformat(),
                "mode": "path",
                "origin_stop": "JSQ",
            },
            headers=headers,
        )

    response = client.post("/home-office/me/infer", headers=headers)

    assert response.status_code == 200
    assert response.json()["home_mode"] == "path"


def test_confirm_sets_confirmed_flag(client):
    token = _signup_and_login(client, email="confirm@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post("/home-office/me/confirm", headers=headers)

    assert response.status_code == 200
    assert response.json()["confirmed"] is True

    # Persisted, not just returned once.
    read_response = client.get("/home-office/me", headers=headers)
    assert read_response.json()["confirmed"] is True
