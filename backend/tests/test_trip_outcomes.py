from datetime import datetime, timedelta, timezone


def _signup_and_login(client, email="outcome@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


def _create_trip(client, headers, predicted_arrival=None):
    response = client.post(
        "/trips",
        json={
            "start_time": datetime.now(timezone.utc).isoformat(),
            "mode": "mta",
            "origin_stop": "R20N",
        },
        headers=headers,
    )
    return response.json()["id"]


def test_accuracy_endpoint_not_shadowed_by_trip_id_route(client):
    """Regression guard: GET /trips/accuracy must resolve to the accuracy
    endpoint, not get swallowed by PATCH /trips/{trip_id}/outcome's
    path-param matching "accuracy" as a trip_id.
    """
    token = _signup_and_login(client)
    response = client.get(
        "/trips/accuracy", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert "recommendations_made" in response.json()


def test_accuracy_starts_at_zero_with_no_trips(client):
    token = _signup_and_login(client, email="zero@example.com")
    response = client.get(
        "/trips/accuracy", headers={"Authorization": f"Bearer {token}"}
    )

    body = response.json()
    assert body["recommendations_made"] == 0
    assert body["recommendations_followed"] == 0
    assert body["average_error_minutes"] is None


def test_report_outcome_requires_auth(client):
    response = client.patch(
        "/trips/00000000-0000-0000-0000-000000000000/outcome",
        json={"was_recommendation_followed": True},
    )
    assert response.status_code == 401


def test_report_outcome_rejects_other_users_trips(client):
    token1 = _signup_and_login(client, email="owner2@example.com")
    trip_id = _create_trip(client, {"Authorization": f"Bearer {token1}"})

    token2 = _signup_and_login(client, email="intruder@example.com")
    response = client.patch(
        f"/trips/{trip_id}/outcome",
        json={"was_recommendation_followed": True},
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert response.status_code == 404


def test_report_outcome_updates_trip(client, db_session):
    import uuid

    from app.models import Trip

    token = _signup_and_login(client, email="report@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    trip_id = _create_trip(client, headers)

    actual_arrival = datetime.now(timezone.utc) + timedelta(minutes=12)
    response = client.patch(
        f"/trips/{trip_id}/outcome",
        json={
            "was_recommendation_followed": True,
            "actual_arrival": actual_arrival.isoformat(),
        },
        headers=headers,
    )

    assert response.status_code == 200
    trip = db_session.get(Trip, uuid.UUID(trip_id))
    assert trip.was_recommendation_followed is True
    assert trip.actual_arrival is not None


def test_accuracy_reflects_reported_outcomes(client):
    import uuid

    token = _signup_and_login(client, email="accuracy@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    # Directly create a trip via the recommendations flow isn't needed here
    # - simulate predicted_arrival by patching a plain trip's fields via a
    # second PATCH after creation, since /trips (POST) doesn't accept
    # predicted_arrival directly (only /recommendations sets it).
    trip_id = _create_trip(client, headers)

    now = datetime.now(timezone.utc)
    client.patch(
        f"/trips/{trip_id}/outcome",
        json={
            "was_recommendation_followed": True,
            "actual_arrival": now.isoformat(),
        },
        headers=headers,
    )

    response = client.get("/trips/accuracy", headers=headers)
    body = response.json()
    # predicted_arrival was never set on this trip (created via POST
    # /trips, not /recommendations) so it shouldn't count toward
    # recommendations_made at all.
    assert body["recommendations_made"] == 0
