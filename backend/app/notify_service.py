"""Sends a push notification to a user's device via Firebase Cloud
Messaging (FCM). Falls back to logging instead of actually sending if no
Firebase project is configured (FIREBASE_CREDENTIALS_JSON unset) - a
recommendation that couldn't be pushed is a degraded experience, not a
reason to crash the notification job for every other eligible user.
"""

import json
import logging

import firebase_admin
from firebase_admin import credentials, exceptions, messaging

from .core.config import settings

logger = logging.getLogger("notify_service")

_firebase_app: firebase_admin.App | None = None
_firebase_init_attempted = False


class PushSendException(Exception):
    pass


def _get_firebase_app() -> firebase_admin.App | None:
    """Lazily initializes the Firebase Admin SDK from
    FIREBASE_CREDENTIALS_JSON on first real send attempt, not at import
    time - so a backend with no Firebase project configured (or in tests,
    which never set this) doesn't fail to even start up. Returns None if
    unconfigured; callers fall back to logging in that case."""
    global _firebase_app, _firebase_init_attempted

    if _firebase_init_attempted:
        return _firebase_app
    _firebase_init_attempted = True

    if not settings.firebase_credentials_json:
        return None

    try:
        cred_dict = json.loads(settings.firebase_credentials_json)
        cred = credentials.Certificate(cred_dict)
        _firebase_app = firebase_admin.initialize_app(cred)
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to initialize Firebase Admin SDK: %s", e)
        _firebase_app = None

    return _firebase_app


def send_push(fcm_token: str, title: str, body: str) -> None:
    """Sends a real push via FCM if a Firebase project is configured;
    otherwise logs what would have been sent (see the module docstring -
    this keeps the notification job usable in dev/test environments and
    before a Firebase project exists).

    Raises PushSendException if FCM itself rejects the send (e.g. the
    token is invalid/unregistered) - the caller (the notification job)
    catches this per-user so one bad token doesn't stop the whole batch.
    """
    app = _get_firebase_app()
    if app is None:
        logger.info("STUB PUSH (no Firebase configured) to token=%s...: %s - %s", fcm_token[:8], title, body)
        return

    # Message.token triggers a DeprecationWarning in this SDK version
    # (favoring the newer .fid param name) but remains the documented,
    # stable way to target a single device - not switching until .fid is
    # more established/documented.
    message = messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(title=title, body=body),
    )
    try:
        message_id = messaging.send(message, app=app)
        logger.info("Sent push %s to token=%s...", message_id, fcm_token[:8])
    except exceptions.FirebaseError as e:
        raise PushSendException(f"FCM send failed: {e}") from e
