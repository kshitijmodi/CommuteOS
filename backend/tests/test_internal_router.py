def test_run_commute_job_returns_503_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", None)

    response = client.post(
        "/internal/run-commute-job", headers={"X-Internal-Secret": "anything"}
    )

    assert response.status_code == 503


def test_run_commute_job_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.post("/internal/run-commute-job")

    assert response.status_code == 401


def test_run_commute_job_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.post(
        "/internal/run-commute-job", headers={"X-Internal-Secret": "wrong-secret"}
    )

    assert response.status_code == 401


def test_run_commute_job_succeeds_with_correct_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    async def fake_send_notifications(db):
        return 3

    monkeypatch.setattr(
        "app.routers.internal.send_notifications_for_all_users", fake_send_notifications
    )

    response = client.post(
        "/internal/run-commute-job", headers={"X-Internal-Secret": "correct-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {"sent_count": 3}


def test_run_commute_job_uses_a_real_session_not_the_test_override(client, monkeypatch):
    """Regression guard: the endpoint opens its own SessionLocal() rather
    than depending on get_db, since it isn't a per-request user endpoint -
    make sure that's still true and it doesn't silently start depending on
    the test's overridden session (which would make this test misleading
    about what runs in production)."""
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    captured_dbs = []

    async def fake_send_notifications(db):
        captured_dbs.append(db)
        return 0

    monkeypatch.setattr(
        "app.routers.internal.send_notifications_for_all_users", fake_send_notifications
    )

    client.post("/internal/run-commute-job", headers={"X-Internal-Secret": "correct-secret"})

    assert len(captured_dbs) == 1
