"""Schedule AI's delivery mechanism (see PRD Phase 3 and
app/schedule_engine.py) - the first genuinely "agentic" piece of the app,
now evolved from a single fixed-time daily fire into a real per-user
timing decision: fires once, ahead of each user's own usual departure
hour (learned from Trip history via schedule_engine.usual_departure_hour_for),
not one clock time for everyone.

Can be run manually (`python -m app.jobs.send_commute_notifications`) or,
in production, is triggered HOURLY via POST /internal/run-commute-job
(see routers/internal.py, .github/workflows/commute-notifications.yml) -
hourly, not a tighter interval, because GitHub Actions cron doesn't
reliably honor sub-hour intervals under platform load (see
OPEN_QUESTIONS.md) - an honest reliability/precision tradeoff, not an
oversight. Every run considers every eligible user and only actually
notifies the ones inside their own personal notification window this
hour, at most once per UTC calendar day (User.last_commute_notification_date).

Eligibility: a user must have (a) a confirmed home/office inference, (b) a
registered fcm_token, (c) enough morning-trip history for
schedule_engine.usual_departure_hour_for to return an hour at all, (d) the
current hour actually being that user's notification window, and (e) not
already notified today.

Message content is now a real Schedule AI decision, not just "here's your
usual route's number": on-time route -> phrased confirmation; a real,
Behavior-AI-baseline-derived delay -> phrased with the actual delay
minutes; no live data for the usual route at all -> Schedule AI delegates
to commute_engine.rank_best (the PRD's "shared brain" - the same named
ranking entry point Commute AI's own recommend_for_station calls, not a
parallel copy of decision_engine.rank_routes) across every home/office
candidate for a real substitute - this IS what "Schedule AI hands off to
the routing engine rather than re-implementing route-picking" means (see
schedule_engine.py's and commute_engine.py's module docstrings).
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..commute_engine import rank_best
from ..llm_phrasing import phrase_schedule_notification
from ..models import Trip, User
from ..notify_service import PushSendException, send_push
from ..recommendation_builder import fetch_candidates, specs_from_home_office
from ..schedule_engine import (
    DisruptionSeverity,
    assess_candidate,
    is_within_notification_window,
    usual_departure_hour_for,
)


async def send_notification_for_user(db: Session, user: User, now: datetime) -> bool:
    """Returns True if a notification was actually sent. False (not an
    error) for any ineligibility reason - one user's ineligibility or bad
    token shouldn't stop the batch from considering everyone else.
    """
    if not user.fcm_token:
        return False

    today = now.date()
    if user.last_commute_notification_date == today:
        return False

    usual_hour = usual_departure_hour_for(db, user.id, is_morning=True)
    if usual_hour is None:
        return False
    if not is_within_notification_window(now.hour, usual_hour):
        return False

    specs = specs_from_home_office(user)
    if not specs:
        return False

    # The "usual route" Schedule AI is checking is specifically the home
    # -leg candidate (morning departure) - specs_from_home_office returns
    # [home, office] when both resolve; home is always first when present.
    home_spec = next((s for s in specs if s.label == user.home_station), specs[0])

    candidates = await fetch_candidates(specs)
    home_candidates = [c for c in candidates if c.label == home_spec.label]
    live_predicted_arrival = None
    if home_candidates and home_candidates[0].arrivals.arrivals:
        live_predicted_arrival = home_candidates[0].arrivals.arrivals[0].arrival_time

    assessment = assess_candidate(
        db, user.id, home_spec.stop_or_station, now.hour, live_predicted_arrival
    )

    substitute = None
    if assessment.severity == DisruptionSeverity.NO_LIVE_DATA:
        ranked = rank_best(candidates, reliability_pref=user.reliability_pref, now=now)
        if not ranked:
            return False  # nothing usable to recommend instead - stay quiet rather than send an empty notification
        substitute = ranked[0]

    message = phrase_schedule_notification(
        assessment,
        usual_label=home_spec.label,
        live_predicted_arrival=live_predicted_arrival,
        substitute=substitute,
    )

    trip = Trip(
        user_id=user.id,
        start_time=now,
        mode=substitute.mode if substitute else home_spec.agency,
        origin_stop=substitute.label if substitute else home_spec.label,
        predicted_arrival=substitute.predicted_arrival if substitute else live_predicted_arrival,
    )
    db.add(trip)

    try:
        send_push(user.fcm_token, title="Time to check your commute", body=message)
    except PushSendException:
        return False

    user.last_commute_notification_date = today
    return True


async def send_notifications_for_all_users(db: Session, now: datetime | None = None) -> int:
    """Returns the number of users actually notified (not the number
    considered - see send_notification_for_user for why many are skipped
    without being an error). [now] defaults to the real current time in
    production; tests pass an explicit value so "is now inside this
    user's window" assertions don't depend on wall-clock timing at the
    moment the test happens to run.
    """
    now = now or datetime.now(timezone.utc)
    user_ids = db.scalars(select(User.id)).all()
    sent_count = 0
    for user_id in user_ids:
        user = db.get(User, user_id)
        if await send_notification_for_user(db, user, now):
            sent_count += 1
    db.commit()
    return sent_count


def main() -> None:
    import asyncio

    from ..core.database import SessionLocal

    db = SessionLocal()
    try:
        sent_count = asyncio.run(send_notifications_for_all_users(db))
        print(f"Sent {sent_count} commute notification(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
