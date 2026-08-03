"""Standalone entrypoint for the proactive commute-notification job - the
first genuinely "agentic" piece of the app: instead of a fixed-time local
reminder (see lib/account/commute_notification_service.dart), this runs
the real decision engine + LLM phrasing against a user's inferred home/
office station and pushes an actual recommendation.

Can be run manually (`python -m app.jobs.send_commute_notifications`) or,
in production, is triggered once daily via POST /internal/run-commute-job
(see routers/internal.py) by a scheduled GitHub Actions workflow. Runs
once for every eligible user at one fixed time (7:45 AM ET) regardless of
each user's actual typical departure time - see OPEN_QUESTIONS.md.

Eligibility: a user must have (a) a confirmed home/office inference (per
the PRD's "confirmed once via a prompt" step - an unconfirmed inference
isn't authoritative enough to act on unprompted), (b) a registered
fcm_token (opted into push), and (c) at least one of home/office station
resolvable to a real CandidateSpec (needs its route_or_direction filled
in for MTA/PATH - see home_office_engine.py's docstring on why that can
be null even when the station itself is known).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models import User
from ..notify_service import PushSendException, send_push
from ..recommendation_builder import build_recommendation, specs_from_home_office


async def send_notification_for_user(db: Session, user: User) -> bool:
    """Returns True if a notification was actually sent. False (not an
    error) for any of: not confirmed, no push token, no usable candidate,
    no live arrivals found for the candidates that do exist, or FCM itself
    rejecting the send (e.g. a stale/invalid token) - one user's bad token
    shouldn't stop the batch from notifying everyone else.
    """
    if not user.fcm_token:
        return False

    specs = specs_from_home_office(user)
    if not specs:
        return False

    outcome = await build_recommendation(db, user, specs)
    if outcome is None:
        return False

    _best, message, _trip = outcome
    try:
        send_push(
            user.fcm_token,
            title="Time to check your commute",
            body=message,
        )
    except PushSendException:
        return False
    return True


async def send_notifications_for_all_users(db: Session) -> int:
    """Returns the number of users actually notified (not the number
    considered - see send_notification_for_user for why many are skipped
    without being an error)."""
    user_ids = db.scalars(select(User.id)).all()
    sent_count = 0
    for user_id in user_ids:
        user = db.get(User, user_id)
        if await send_notification_for_user(db, user):
            sent_count += 1
    db.commit()
    return sent_count


def main() -> None:
    import asyncio

    db = SessionLocal()
    try:
        sent_count = asyncio.run(send_notifications_for_all_users(db))
        print(f"Sent {sent_count} commute notification(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
