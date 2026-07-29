def test_signup_creates_user_and_preferences_row(client, db_session):
    from app.models import Preference, User

    response = client.post(
        "/auth/signup",
        json={"email": "commuter@example.com", "password": "correct-horse-battery"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "commuter@example.com"
    assert body["reliability_pref"] == 0.5
    assert "hashed_password" not in body  # never leak the hash to the client

    user = db_session.query(User).filter_by(email="commuter@example.com").one()
    assert user.hashed_password != "correct-horse-battery"  # actually hashed

    prefs = db_session.query(Preference).filter_by(user_id=user.id).one_or_none()
    assert prefs is not None


def test_signup_rejects_duplicate_email(client):
    payload = {"email": "dup@example.com", "password": "password123"}
    first = client.post("/auth/signup", json=payload)
    second = client.post("/auth/signup", json=payload)

    assert first.status_code == 201
    assert second.status_code == 400


def test_login_succeeds_with_correct_password(client):
    client.post(
        "/auth/signup",
        json={"email": "login@example.com", "password": "hunter2"},
    )

    response = client.post(
        "/auth/login",
        data={"username": "login@example.com", "password": "hunter2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 0


def test_login_fails_with_wrong_password(client):
    client.post(
        "/auth/signup",
        json={"email": "wrongpw@example.com", "password": "correctpassword"},
    )

    response = client.post(
        "/auth/login",
        data={"username": "wrongpw@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401


def test_login_fails_for_unknown_email(client):
    response = client.post(
        "/auth/login",
        data={"username": "nobody@example.com", "password": "whatever"},
    )

    assert response.status_code == 401


def test_authenticated_endpoint_requires_token(client):
    response = client.get("/users/me")
    assert response.status_code == 401


def test_authenticated_endpoint_returns_current_user(client):
    client.post(
        "/auth/signup",
        json={"email": "me@example.com", "password": "hunter2"},
    )
    login_response = client.post(
        "/auth/login",
        data={"username": "me@example.com", "password": "hunter2"},
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


def test_authenticated_endpoint_rejects_garbage_token(client):
    response = client.get(
        "/users/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401
