"""Sends a push notification to a user's device. This is a stub - it logs
what it would send rather than actually calling Firebase Cloud Messaging,
by explicit choice (see OPEN_QUESTIONS.md): FCM setup requires creating a
real Firebase project (an account-creation step only the user can do,
same as the earlier Neon/Render setup), so the notification pipeline
(scheduled job -> decision engine -> LLM phrasing -> this module) is being
built and tested end-to-end first, with the real FCM call swapped in once
project credentials exist. `send_push` is the one function that needs to
change when that happens - nothing else in the pipeline depends on how
the push actually gets delivered.
"""

import logging

logger = logging.getLogger("notify_service")


class PushSendException(Exception):
    pass


def send_push(fcm_token: str, title: str, body: str) -> None:
    """Sends a push notification. Stub implementation: logs instead of
    calling FCM. Swap this function's body for a real
    firebase_admin.messaging.send(...) call once a Firebase project and
    service account credentials exist - callers (the notification job)
    don't need to change.
    """
    logger.info("STUB PUSH to token=%s...: %s - %s", fcm_token[:8], title, body)
