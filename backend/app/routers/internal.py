"""Internal-only endpoints - not part of the mobile app's API surface, not
meant to be called by any user. Currently just the commute-notification
job trigger (see app/jobs/send_commute_notifications.py's docstring on
why this needs an external trigger at all: Render's free tier has no
built-in cron, and the web service itself spins down when idle).
"""

import hmac

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from ..core.config import settings
from ..core.database import SessionLocal
from ..jobs.send_commute_notifications import send_notifications_for_all_users

router = APIRouter(prefix="/internal", tags=["internal"])


class RunCommuteJobResponse(BaseModel):
    sent_count: int


def _verify_secret(x_internal_secret: str | None) -> None:
    """Constant-time comparison (hmac.compare_digest) - this guards a real
    action (sending push notifications to every eligible user), so a
    timing side-channel on string comparison is worth avoiding even though
    the practical risk here is low."""
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
