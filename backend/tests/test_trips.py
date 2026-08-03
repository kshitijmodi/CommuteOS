def _signup_and_login(client, email="tripper@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


def test_create_trip_requires_auth(client):
    response = client.post(
        "/trips",
        json={
            "start_time": "2026-07-29T08:15:00Z",
            "mode": "mta",
            "origin_stop": "R20N",
        },
    )
    assert response.status_code == 401


def test_create_trip_without_destination(client):
    token = _signup_and_login(client)

    response = client.post(
        "/trips",
        json={
            "start_time": "2026-07-29T08:15:00Z",
            "mode": "mta",
            "origin_stop": "R20N",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["origin_stop"] == "R20N"
    assert body["dest_stop"] is None
    assert body["mode"] == "mta"


def test_create_trip_with_destination(client):
    token = _signup_and_login(client)

    response = client.post(
        "/trips",
        json={
            "start_time": "2026-07-29T08:15:00Z",
            "mode": "path",
            "origin_stop": "JSQ",
            "dest_stop": "WTC",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["dest_stop"] == "WTC"


def test_create_trip_with_route_or_direction(client):
    token = _signup_and_login(client, email="routedir@example.com")

    response = client.post(
        "/trips",
        json={
            "start_time": "2026-07-29T08:15:00Z",
            "mode": "mta",
            "origin_stop": "R20N",
            "route_or_direction": "N",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["route_or_direction"] == "N"


def test_created_trip_is_attributed_to_the_authenticated_user(client, db_session):
    from app.models import Trip, User

    token = _signup_and_login(client, email="owner@example.com")

    client.post(
        "/trips",
        json={
            "start_time": "2026-07-29T08:15:00Z",
            "mode": "mta",
            "origin_stop": "R20N",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    user = db_session.query(User).filter_by(email="owner@example.com").one()
    trip = db_session.query(Trip).filter_by(user_id=user.id).one()
    assert trip.origin_stop == "R20N"
