from datetime import datetime, timedelta, timezone


def _signup_and_login(client, email="behaviorapi@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post(
        "/auth/login", data={"username": email, "password": password}
    )
    return login.json()["access_token"]


def test_read_my_behavior_requires_auth(client):
    response = client.get("/behavior/me")
    assert response.status_code == 401


def test_read_my_behavior_is_empty_for_new_user(client):
    token = _signup_and_login(client)
    response = client.get(
        "/behavior/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["feed_accuracy"] == []
    assert body["direction_choices"] == []
    assert body["timing_buffers"] == []


def test_read_my_behavior_surfaces_direction_choices(client, db_session):
    from app.models import Trip, User

    token = _signup_and_login(client, email="directions@example.com")
    user = db_session.query(User).filter(User.email == "directions@example.com").one()

    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=datetime.now(timezone.utc).replace(hour=8) - timedelta(days=i),
                mode="mta",
                origin_stop="JSQ",
                route_or_direction="N",
            )
        )
    db_session.commit()

    response = client.get(
        "/behavior/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["direction_choices"]) == 1
    assert body["direction_choices"][0]["most_common_route_or_direction"] == "N"
    assert body["direction_choices"][0]["sample_count"] == 3
