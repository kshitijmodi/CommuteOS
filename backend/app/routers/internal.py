"""Internal-only endpoints - not part of the mobile app's API surface, not
meant to be called by any user. Both endpoints here trigger a nightly
batch job that would otherwise have no way to run at all: Render's free
tier has no built-in cron, and the web service itself spins down when
idle, so nothing hosted there can reliably self-schedule.
"""

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from ..core.config import settings
from ..core.database import SessionLocal
from ..home_office_engine import infer_home_and_office_for_all_users
from ..jobs.send_commute_notifications import send_notifications_for_all_users
from ..preference_engine import recompute_all_preferences

router = APIRouter(prefix="/internal", tags=["internal"])


class RunCommuteJobResponse(BaseModel):
    sent_count: int


class RunPreferenceRecomputeResponse(BaseModel):
    preferences_recomputed: int
    home_office_inferred: int


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
