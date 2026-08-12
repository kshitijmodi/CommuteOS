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


def test_run_preference_recompute_job_returns_503_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", None)

    response = client.post(
        "/internal/run-preference-recompute-job", headers={"X-Internal-Secret": "anything"}
    )

    assert response.status_code == 503


def test_run_preference_recompute_job_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.post("/internal/run-preference-recompute-job")

    assert response.status_code == 401


def test_run_preference_recompute_job_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.post(
        "/internal/run-preference-recompute-job", headers={"X-Internal-Secret": "wrong-secret"}
    )

    assert response.status_code == 401


def test_run_preference_recompute_job_succeeds_with_correct_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    def fake_recompute_all_preferences(db):
        return 2

    def fake_infer_home_and_office_for_all_users(db):
        return 1

    monkeypatch.setattr(
        "app.routers.internal.recompute_all_preferences", fake_recompute_all_preferences
    )
    monkeypatch.setattr(
        "app.routers.internal.infer_home_and_office_for_all_users",
        fake_infer_home_and_office_for_all_users,
    )

    response = client.post(
        "/internal/run-preference-recompute-job",
        headers={"X-Internal-Secret": "correct-secret"},
    )

    assert response.status_code == 200
    assert response.json() == {"preferences_recomputed": 2, "home_office_inferred": 1}


def test_run_preference_recompute_job_uses_a_real_session_not_the_test_override(
    client, monkeypatch
):
    """Same regression guard as the commute-job endpoint above - this job
    also isn't a per-request user endpoint, so it must open its own
    SessionLocal() rather than silently depending on get_db's test
    override."""
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    captured_dbs = []

    def fake_recompute_all_preferences(db):
        captured_dbs.append(db)
        return 0

    def fake_infer_home_and_office_for_all_users(db):
        captured_dbs.append(db)
        return 0

    monkeypatch.setattr(
        "app.routers.internal.recompute_all_preferences", fake_recompute_all_preferences
    )
    monkeypatch.setattr(
        "app.routers.internal.infer_home_and_office_for_all_users",
        fake_infer_home_and_office_for_all_users,
    )

    client.post(
        "/internal/run-preference-recompute-job",
        headers={"X-Internal-Secret": "correct-secret"},
    )

    assert len(captured_dbs) == 2


# --- Per-user AI status diagnostic (2026-08-12) ---
# Real user report: "I keep walking toward Journal Square PATH but never
# get anything from Schedule AI/Commute AI - is Behavior AI even
# gathering anything?" Answers with real numbers, read straight from the
# same tables/functions the real jobs use, rather than a guess.


def test_user_ai_status_returns_503_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", None)

    response = client.get(
        "/internal/user-ai-status",
        params={"email": "someone@example.com"},
        headers={"X-Internal-Secret": "anything"},
    )

    assert response.status_code == 503


def test_user_ai_status_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.get("/internal/user-ai-status", params={"email": "someone@example.com"})

    assert response.status_code == 401


def test_user_ai_status_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.get(
        "/internal/user-ai-status",
        params={"email": "someone@example.com"},
        headers={"X-Internal-Secret": "wrong-secret"},
    )

    assert response.status_code == 401


def test_user_ai_status_404s_for_an_unknown_email(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.get(
        "/internal/user-ai-status",
        params={"email": "nobody-real@example.com"},
        headers={"X-Internal-Secret": "correct-secret"},
    )

    assert response.status_code == 404


def test_user_ai_status_reports_real_trip_count_and_engine_signals_with_correct_secret(
    client, monkeypatch
):
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.core.database import SessionLocal
    from sqlalchemy import select

    from app.models import Trip, User

    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")
    # Same regression-guarded reasoning as the other job/debug endpoints -
    # this one opens its own SessionLocal(), so seed through that same
    # real path, not the test's overridden get_db session.
    real_db = SessionLocal()
    user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="x")
    real_db.add(user)
    real_db.commit()
    user_id, user_email = user.id, user.email

    # 3 morning trips from the same station/slot - enough to clear every
    # engine's real _MIN_SAMPLES/_MIN_TRIPS_PER_SLOT threshold (3). This
    # endpoint deliberately opens its own SessionLocal() against the REAL
    # local dev Postgres (same regression-guarded pattern as the other
    # job/debug endpoints), not the test's in-memory SQLite override -
    # worth noting real Postgres reads a tz-aware datetime back
    # session-timezone-converted (not preserved as UTC the way SQLite's
    # naive passthrough does), so the read-back .hour can differ from
    # what was inserted; read it back once here to get the real value
    # this session's Postgres will actually report, rather than assuming
    # the inserted hour survives unchanged.
    inserted_start = datetime.now(timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
    for i in range(3):
        start = inserted_start - timedelta(days=i)
        real_db.add(
            Trip(
                user_id=user_id,
                start_time=start,
                mode="path",
                origin_stop="JSQ",
                route_or_direction="ToNY",
                predicted_arrival=start + timedelta(minutes=5),
                actual_arrival=start + timedelta(minutes=7),
            )
        )
    real_db.commit()
    real_trip = real_db.scalars(select(Trip).where(Trip.user_id == user_id)).first()
    expected_hour = real_trip.start_time.hour
    real_db.close()

    response = client.get(
        "/internal/user-ai-status",
        params={"email": user_email},
        headers={"X-Internal-Secret": "correct-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trip_count"] == 3
    assert body["usual_morning_departure_hour"] == expected_hour
    assert len(body["feed_accuracy"]) == 1
    assert body["feed_accuracy"][0]["sample_count"] == 3
    assert len(body["direction_choices"]) == 1
    assert body["direction_choices"][0]["most_common_route_or_direction"] == "ToNY"


def test_user_ai_status_reports_zero_trips_honestly_not_an_error(client, monkeypatch):
    import uuid

    from app.core.database import SessionLocal
    from app.models import User

    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")
    real_db = SessionLocal()
    user = User(email=f"{uuid.uuid4()}@example.com", hashed_password="x")
    real_db.add(user)
    real_db.commit()
    user_email = user.email
    real_db.close()

    response = client.get(
        "/internal/user-ai-status",
        params={"email": user_email},
        headers={"X-Internal-Secret": "correct-secret"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["trip_count"] == 0
    assert body["usual_morning_departure_hour"] is None
    assert body["feed_accuracy"] == []
    assert body["direction_choices"] == []
    assert body["timing_buffers"] == []


# --- NJT bus routes refresh job (2026-08-11) ---
# Keeps the trip_id -> route mapping fresh - see
# transit/njt_bus.py's module docstring for the real bug (NJT reshuffles
# real bus trip_ids completely within days, silently degrading arrivals
# to a "Bus" placeholder or nothing at all).


def test_run_njt_bus_routes_refresh_job_returns_503_when_secret_not_configured(
    client, monkeypatch
):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", None)

    response = client.post(
        "/internal/run-njt-bus-routes-refresh-job", headers={"X-Internal-Secret": "anything"}
    )

    assert response.status_code == 503


def test_run_njt_bus_routes_refresh_job_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.post("/internal/run-njt-bus-routes-refresh-job")

    assert response.status_code == 401


def test_run_njt_bus_routes_refresh_job_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.post(
        "/internal/run-njt-bus-routes-refresh-job", headers={"X-Internal-Secret": "wrong-secret"}
    )

    assert response.status_code == 401


def test_run_njt_bus_routes_refresh_job_succeeds_with_correct_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    async def fake_refresh():
        return 35079

    monkeypatch.setattr(
        "app.routers.internal.run_njt_bus_routes_refresh", fake_refresh
    )

    response = client.post(
        "/internal/run-njt-bus-routes-refresh-job", headers={"X-Internal-Secret": "correct-secret"}
    )

    assert response.status_code == 200
    assert response.json() == {"trip_id_rows_loaded": 35079}


def test_run_njt_bus_routes_refresh_job_surfaces_a_real_feed_failure_as_502(client, monkeypatch):
    # Unlike the other two jobs (which skip ineligible users silently),
    # a failure here means the mapping either refreshed or it didn't -
    # surface it loudly rather than reporting success with nothing done.
    from app.transit.njt_bus import NjtBusFeedException

    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    async def fake_refresh():
        raise NjtBusFeedException("NJT bus authentication failed")

    monkeypatch.setattr(
        "app.routers.internal.run_njt_bus_routes_refresh", fake_refresh
    )

    response = client.post(
        "/internal/run-njt-bus-routes-refresh-job", headers={"X-Internal-Secret": "correct-secret"}
    )

    assert response.status_code == 502


# --- Real chat-transcript debug endpoint (2026-08-10) ---
# Added for a real, narrow reason: diagnosing a live-reported Chat AI bug
# needs the actual production transcript, and there's no other way to
# read it (no local machine has the real DATABASE_URL, and Render's REST
# API has no remote-shell/exec for a web service). Read-only, same
# secret-guarded pattern as the job triggers.


def test_recent_chat_messages_returns_503_when_secret_not_configured(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", None)

    response = client.get(
        "/internal/recent-chat-messages", headers={"X-Internal-Secret": "anything"}
    )

    assert response.status_code == 503


def test_recent_chat_messages_rejects_missing_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.get("/internal/recent-chat-messages")

    assert response.status_code == 401


def test_recent_chat_messages_rejects_wrong_secret(client, monkeypatch):
    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")

    response = client.get(
        "/internal/recent-chat-messages", headers={"X-Internal-Secret": "wrong-secret"}
    )

    assert response.status_code == 401


def test_recent_chat_messages_returns_real_recent_turns_with_correct_secret(
    client, monkeypatch
):
    import uuid

    from app.core.database import SessionLocal
    from app.models import ChatMessage, ChatSession

    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")
    # This endpoint opens its own SessionLocal() (same regression-guarded
    # reasoning as the job endpoints above), not the test's overridden
    # get_db session - seed through the SAME real path it actually reads
    # from, or this test would pass without proving anything real.
    real_db = SessionLocal()
    session_id = uuid.uuid4()
    real_db.add(ChatSession(id=session_id))
    real_db.commit()
    real_db.add(ChatMessage(session_id=session_id, role="user", content="what's next from Grove Street"))
    real_db.add(
        ChatMessage(
            session_id=session_id,
            role="assistant",
            content="The next PATH train is in 5 min.",
            station_agency="path",
            station_code="GRV",
        )
    )
    real_db.commit()
    real_db.close()

    response = client.get(
        "/internal/recent-chat-messages", headers={"X-Internal-Secret": "correct-secret"}
    )

    assert response.status_code == 200
    body = response.json()
    contents = [row["content"] for row in body]
    assert "what's next from Grove Street" in contents
    assert "The next PATH train is in 5 min." in contents


def test_recent_chat_messages_excludes_turns_older_than_the_window(client, monkeypatch):
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.core.database import SessionLocal
    from app.models import ChatMessage, ChatSession

    monkeypatch.setattr("app.routers.internal.settings.internal_job_secret", "correct-secret")
    real_db = SessionLocal()
    session_id = uuid.uuid4()
    old_time = datetime.now(timezone.utc) - timedelta(hours=2)
    real_db.add(ChatSession(id=session_id))
    real_db.commit()
    real_db.add(
        ChatMessage(
            session_id=session_id,
            role="user",
            content="a real old message outside the default 5-minute window",
            created_at=old_time,
        )
    )
    real_db.commit()
    real_db.close()

    response = client.get(
        "/internal/recent-chat-messages", headers={"X-Internal-Secret": "correct-secret"}
    )

    assert response.status_code == 200
    contents = [row["content"] for row in response.json()]
    assert "a real old message outside the default 5-minute window" not in contents
