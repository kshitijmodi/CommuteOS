from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import Preference, Trip, User
from ..preference_engine import MIN_TRIPS_FOR_WALKING_TOLERANCE, recompute_preferences_for_user

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferenceRead(BaseModel):
    walking_tolerance_m: float
    transfer_aversion_score: float
    reliability_pref: float
    trip_count: int
    # Whether walking_tolerance_m reflects real trip history or is still
    # just the untouched schema default - see preference_engine.py's
    # MIN_TRIPS_FOR_WALKING_TOLERANCE. transfer_aversion_score has no
    # equivalent flag: it's always the neutral default today regardless of
    # trip_count (see that module's docstring on why it can't be computed
    # yet), so the client should treat it as never-yet-learned rather than
    # gate it on this trip count.
    walking_tolerance_learned: bool

    model_config = {"from_attributes": True}


def _read_preference(current_user: User, preference: Preference, db: Session) -> PreferenceRead:
    trip_count = db.scalar(
        select(func.count()).select_from(Trip).where(Trip.user_id == current_user.id)
    )
    return PreferenceRead(
        walking_tolerance_m=preference.walking_tolerance_m,
        transfer_aversion_score=preference.transfer_aversion_score,
        reliability_pref=current_user.reliability_pref,
        trip_count=trip_count,
        walking_tolerance_learned=trip_count >= MIN_TRIPS_FOR_WALKING_TOLERANCE,
    )


@router.get("/me", response_model=PreferenceRead)
def read_my_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preference = db.get(Preference, current_user.id)
    return _read_preference(current_user, preference, db)


@router.post("/me/recompute", response_model=PreferenceRead)
def recompute_my_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually triggers what the nightly batch job (see
    app/jobs/recompute_preferences.py) otherwise does on a schedule -
    useful for demoing/testing without waiting for the actual schedule.
    """
    preference = recompute_preferences_for_user(db, current_user.id)
    db.commit()
    return _read_preference(current_user, preference, db)
