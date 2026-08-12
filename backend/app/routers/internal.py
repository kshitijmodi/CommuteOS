"""Internal-only endpoints - not part of the mobile app's API surface, not
meant to be called by any user. The two job-trigger endpoints exist
because Render's free tier has no built-in cron and the web service
spins down when idle, so nothing hosted there can reliably self-schedule.
The chat-debug endpoint exists for a narrower, real reason: diagnosing a
live Chat AI bug report needs the actual transcript, and there's no
other way to read it - no local dev machine has the real production
DATABASE_URL, and Render's REST API has no remote-shell/exec endpoint
for a web service. Same secret-guarded pattern as the job triggers, kept
deliberately read-only (no action it triggers, nothing it can corrupt).
"""

import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select

from ..behavior_engine import (
    direction_choices_for_user,
    feed_accuracy_for_user,
    timing_buffers_for_user,
)
from ..core.config import settings
from ..core.database import SessionLocal
from ..home_office_engine import infer_home_and_office_for_all_users
from ..jobs.refresh_njt_bus_routes import run as run_njt_bus_routes_refresh
from ..jobs.send_commute_notifications import send_notifications_for_all_users
from ..models import ChatMessage, Trip, User
from ..preference_engine import recompute_all_preferences
from ..schedule_engine import usual_departure_hour_for
from ..transit.njt_bus import NjtBusFeedException

router = APIRouter(prefix="/internal", tags=["internal"])


class RunCommuteJobResponse(BaseModel):
    sent_count: int


class RunPreferenceRecomputeResponse(BaseModel):
    preferences_recomputed: int
    home_office_inferred: int


class RunNjtBusRoutesRefreshResponse(BaseModel):
    trip_id_rows_loaded: int


def _verify_secret(x_internal_secret: str | None) -> None:
    """Constant-time comparison (hmac.compare_digest) - this guards real
    actions (sending push notifications / rewriting every user's learned
    preferences), so a timing side-channel on string comparison is worth
    avoiding even though the practical risk here is low."""
    if not settings.internal_job_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal job trigger is not configured",
        )
    if not x_internal_secret or not hmac.compare_digest(
        x_internal_secret, settings.internal_job_secret
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")


@router.post("/run-commute-job", response_model=RunCommuteJobResponse)
async def run_commute_job(x_internal_secret: str | None = Header(default=None)):
    _verify_secret(x_internal_secret)

    db = SessionLocal()
    try:
        sent_count = await send_notifications_for_all_users(db)
    finally:
        db.close()

    return RunCommuteJobResponse(sent_count=sent_count)


@router.post("/run-preference-recompute-job", response_model=RunPreferenceRecomputeResponse)
async def run_preference_recompute_job(x_internal_secret: str | None = Header(default=None)):
    _verify_secret(x_internal_secret)

    db = SessionLocal()
    try:
        preferences_recomputed = recompute_all_preferences(db)
        home_office_inferred = infer_home_and_office_for_all_users(db)
    finally:
        db.close()

    return RunPreferenceRecomputeResponse(
        preferences_recomputed=preferences_recomputed,
        home_office_inferred=home_office_inferred,
    )


@router.post("/run-njt-bus-routes-refresh-job", response_model=RunNjtBusRoutesRefreshResponse)
async def run_njt_bus_routes_refresh_job(x_internal_secret: str | None = Header(default=None)):
    """See jobs/refresh_njt_bus_routes.py - NJT reshuffles real bus
    trip_ids fast enough that the bundled CSV baseline goes stale within
    about a week and a half, silently degrading every NJT bus arrival to
    a "Bus" placeholder (or missing entirely). A real failure here
    (raised as NjtBusFeedException - bad credentials, malformed feed) is
    surfaced as a 502 rather than swallowed, unlike the other two jobs
    above which skip ineligible users silently - there's no per-item
    partial-success concept here, the mapping either refreshed or it
    didn't, and a failure means the PREVIOUS in-memory mapping (whatever
    was loaded at process start or the last successful refresh) is still
    what's actively serving real requests until this succeeds.
    """
    _verify_secret(x_internal_secret)

    try:
        trip_id_rows_loaded = await run_njt_bus_routes_refresh()
    except NjtBusFeedException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)) from e

    return RunNjtBusRoutesRefreshResponse(trip_id_rows_loaded=trip_id_rows_loaded)


class TripDebugRow(BaseModel):
    id: str
    start_time: datetime
    mode: str
    origin_stop: str
    route_or_direction: str | None
    predicted_arrival: datetime | None
    actual_arrival: datetime | None
    left_at: datetime | None


class FeedAccuracyDebugRow(BaseModel):
    mode: str
    origin_stop: str
    time_slot: int
    sample_count: int
    average_error_minutes: float


class DirectionChoiceDebugRow(BaseModel):
    origin_stop: str
    time_slot: int
    sample_count: int
    most_common_route_or_direction: str
    confidence: float


class TimingBufferDebugRow(BaseModel):
    origin_stop: str
    time_slot: int
    sample_count: int
    average_buffer_minutes: float


class UserAiStatusResponse(BaseModel):
    """Answers "is Behavior/Schedule/Commute AI doing anything for me" with
    real numbers rather than a guess - every field here is read straight
    from the same tables/functions the real jobs use, not a re-derived
    summary that could disagree with what's actually running in
    production.
    """

    email: str
    trip_count: int
    recent_trips: list[TripDebugRow]

    home_station: str | None
    home_station_confirmed: bool
    office_station: str | None
    fcm_token_registered: bool

    usual_morning_departure_hour: int | None
    usual_evening_departure_hour: int | None

    feed_accuracy: list[FeedAccuracyDebugRow]
    direction_choices: list[DirectionChoiceDebugRow]
    timing_buffers: list[TimingBufferDebugRow]


@router.get("/user-ai-status", response_model=UserAiStatusResponse)
async def user_ai_status(
    email: str = Query(...),
    x_internal_secret: str | None = Header(default=None),
):
    """Real diagnostic for "is Behavior/Schedule/Commute AI working for
    me" - reads this one user's actual Trip history and re-runs the exact
    same behavior_engine/schedule_engine/home_office_engine functions the
    real scheduled jobs call, so what this reports can't disagree with
    what's actually happening in production. Read-only, same
    secret-guarded pattern as the other internal endpoints - exposes one
    real user's trip history by email, so treat the secret with the same
    care as any other internal endpoint (this is more sensitive than the
    chat-transcript debug endpoint, which has no easy way to target one
    specific person).
    """
    _verify_secret(x_internal_secret)

    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No user with that email")

        trips = db.scalars(
            select(Trip)
            .where(Trip.user_id == user.id)
            .order_by(Trip.start_time.desc())
        ).all()

        return UserAiStatusResponse(
            email=user.email,
            trip_count=len(trips),
            recent_trips=[
                TripDebugRow(
                    id=str(t.id),
                    start_time=t.start_time,
                    mode=t.mode,
                    origin_stop=t.origin_stop,
                    route_or_direction=t.route_or_direction,
                    predicted_arrival=t.predicted_arrival,
                    actual_arrival=t.actual_arrival,
                    left_at=t.left_at,
                )
                for t in trips[:20]
            ],
            home_station=user.home_station,
            home_station_confirmed=user.home_office_confirmed,
            office_station=user.office_station,
            fcm_token_registered=user.fcm_token is not None,
            usual_morning_departure_hour=usual_departure_hour_for(db, user.id, is_morning=True),
            usual_evening_departure_hour=usual_departure_hour_for(db, user.id, is_morning=False),
            feed_accuracy=[
                FeedAccuracyDebugRow(**vars(r)) for r in feed_accuracy_for_user(db, user.id)
            ],
            direction_choices=[
                DirectionChoiceDebugRow(**vars(r)) for r in direction_choices_for_user(db, user.id)
            ],
            timing_buffers=[
                TimingBufferDebugRow(**vars(r)) for r in timing_buffers_for_user(db, user.id)
            ],
        )
    finally:
        db.close()


class ChatMessageDebugRow(BaseModel):
    session_id: str
    role: str
    content: str
    station_agency: str | None
    station_code: str | None
    created_at: datetime


@router.get("/recent-chat-messages", response_model=list[ChatMessageDebugRow])
async def recent_chat_messages(
    x_internal_secret: str | None = Header(default=None),
    minutes: int = Query(default=5, ge=1, le=180),
):
    """Real chat turns from the last [minutes] minutes, newest first -
    read-only, for debugging a live-reported Chat AI bug against the
    actual production transcript rather than a guess or a reproduction
    that might not match what really happened. No session_id filter
    exposed here deliberately - the app's UI never shows the user their
    own session id, so there's nothing for a caller to target one
    specific conversation with; this always returns everything recent,
    across every session, for manual inspection.
    """
    _verify_secret(x_internal_secret)

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    db = SessionLocal()
    try:
        rows = db.scalars(
            select(ChatMessage)
            .where(ChatMessage.created_at >= cutoff)
            .order_by(ChatMessage.id.desc())
        ).all()
    finally:
        db.close()

    return [
        ChatMessageDebugRow(
            session_id=str(row.session_id),
            role=row.role,
            content=row.content,
            station_agency=row.station_agency,
            station_code=row.station_code,
            created_at=row.created_at,
        )
        for row in rows
    ]
