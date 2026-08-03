"""Standalone entrypoint for the proactive commute-notification job - the
first genuinely "agentic" piece of the app: instead of a fixed-time local
reminder (see lib/account/commute_notification_service.dart), this runs
the real decision engine + LLM phrasing against a user's inferred home/
office station and pushes an actual recommendation.

Run manually for now (`python -m app.jobs.send_commute_notifications`);
wiring this to a real schedule (so it runs automatically near each user's
usual departure time, not on a developer's command) is a deployment
concern tracked in OPEN_QUESTIONS.md, same as the nightly preference job.
Currently runs once for every eligible user regardless of local time of
day - a real scheduled version would need per-user timezone/departure-
time awareness to avoid notifying at 3am.

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
from ..recommendation_builder import CandidateSpec, build_recommendation


def _candidate_spec_for(
    station: str | None, mode: str | None, route_or_direction: str | None
) -> CandidateSpec | None:
    if station is None or mode is None:
        return None
    if mode in ("mta", "path") and not route_or_direction:
        # Known station, but no route/direction ever captured for it (see
        # the module docstring) - can't call MTA/PATH's get_arrivals
        # without one, so this user can't be auto-recommended yet.
        return None
    return CandidateSpec(
        agency=mode,
        label=station,
        stop_or_station=station,
        route_or_direction=route_or_direction or "",
    )


async def send_notification_for_user(db: Session, user: User) -> bool:
    """Returns True if a notification was actually sent. False (not an
    error) for any of: not confirmed, no push token, no usable candidate,
    no live arrivals found for the candidates that do exist, or FCM itself
    rejecting the send (e.g. a stale/invalid token) - one user's bad token
    shouldn't stop the batch from notifying everyone else.
    """
    if not user.home_office_confirmed or not user.fcm_token:
        return False

    specs = [
        spec
        for spec in (
            _candidate_spec_for(user.home_station, user.home_mode, user.home_route_or_direction),
            _candidate_spec_for(
                user.office_station, user.office_mode, user.office_route_or_direction
            ),
        )
        if spec is not None
    ]
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
