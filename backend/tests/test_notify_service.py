import pytest
from firebase_admin import exceptions

from app import notify_service


@pytest.fixture(autouse=True)
def _reset_firebase_app_cache():
    """The module caches its initialized Firebase app at module scope -
    reset between tests so one test's mocked/real app doesn't leak into
    another's."""
    notify_service._firebase_app = None
    notify_service._firebase_init_attempted = False
    yield
    notify_service._firebase_app = None
    notify_service._firebase_init_attempted = False


def test_falls_back_to_logging_when_unconfigured(monkeypatch, caplog):
    monkeypatch.setattr(notify_service.settings, "firebase_credentials_json", None)

    with caplog.at_level("INFO"):
        notify_service.send_push("some-token", "Title", "Body")

    assert "STUB PUSH" in caplog.text


def test_falls_back_to_logging_on_malformed_credentials(monkeypatch, caplog):
    monkeypatch.setattr(notify_service.settings, "firebase_credentials_json", "not valid json")

    with caplog.at_level("INFO"):
        notify_service.send_push("some-token", "Title", "Body")

    assert "STUB PUSH" in caplog.text


def test_sends_real_push_when_configured(monkeypatch):
    monkeypatch.setattr(
        notify_service.settings, "firebase_credentials_json", '{"type": "service_account"}'
    )

    fake_app = object()
    monkeypatch.setattr(notify_service.credentials, "Certificate", lambda d: "fake-cred")
    monkeypatch.setattr(notify_service.firebase_admin, "initialize_app", lambda cred: fake_app)

    sent = {}

    def fake_send(message, app=None):
        sent["token"] = message.token
        sent["title"] = message.notification.title
        sent["body"] = message.notification.body
        sent["app"] = app
        return "message-id-123"

    monkeypatch.setattr(notify_service.messaging, "send", fake_send)

    notify_service.send_push("device-token", "Time to check", "Your train is delayed")

    assert sent["token"] == "device-token"
    assert sent["title"] == "Time to check"
    assert sent["body"] == "Your train is delayed"
    assert sent["app"] is fake_app


def test_raises_push_send_exception_on_fcm_error(monkeypatch):
    monkeypatch.setattr(
        notify_service.settings, "firebase_credentials_json", '{"type": "service_account"}'
    )
    monkeypatch.setattr(notify_service.credentials, "Certificate", lambda d: "fake-cred")
    monkeypatch.setattr(notify_service.firebase_admin, "initialize_app", lambda cred: object())

    def fake_send(message, app=None):
        raise exceptions.InvalidArgumentError("bad token")

    monkeypatch.setattr(notify_service.messaging, "send", fake_send)

    with pytest.raises(notify_service.PushSendException):
        notify_service.send_push("bad-token", "Title", "Body")


def test_firebase_app_is_only_initialized_once(monkeypatch):
    monkeypatch.setattr(
        notify_service.settings, "firebase_credentials_json", '{"type": "service_account"}'
    )
    monkeypatch.setattr(notify_service.credentials, "Certificate", lambda d: "fake-cred")

    init_count = {"n": 0}

    def fake_initialize_app(cred):
        init_count["n"] += 1
        return object()

    monkeypatch.setattr(notify_service.firebase_admin, "initialize_app", fake_initialize_app)
    monkeypatch.setattr(notify_service.messaging, "send", lambda message, app=None: "id")

    notify_service.send_push("token1", "Title", "Body")
    notify_service.send_push("token2", "Title", "Body")

    assert init_count["n"] == 1
