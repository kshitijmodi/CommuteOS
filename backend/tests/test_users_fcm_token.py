def _signup_and_login(client, email="pushuser@example.com", password="hunter22"):
    client.post("/auth/signup", json={"email": email, "password": password})
    login = client.post("/auth/login", data={"username": email, "password": password})
    return login.json()["access_token"]


def test_update_fcm_token_requires_auth(client):
    response = client.put("/users/me/fcm-token", json={"fcm_token": "abc123"})
    assert response.status_code == 401


def test_update_fcm_token_sets_the_token(client, db_session):
    from app.models import User

    token = _signup_and_login(client)

    response = client.put(
        "/users/me/fcm-token",
        json={"fcm_token": "device-token-abc"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    user = db_session.query(User).filter_by(email="pushuser@example.com").one()
    assert user.fcm_token == "device-token-abc"


def test_update_fcm_token_response_does_not_leak_the_token(client):
    token = _signup_and_login(client, email="notleak@example.com")

    response = client.put(
        "/users/me/fcm-token",
        json={"fcm_token": "device-token-abc"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert "fcm_token" not in response.json()
