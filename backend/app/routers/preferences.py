from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import Preference, User
from ..preference_engine import recompute_preferences_for_user

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferenceRead(BaseModel):
    walking_tolerance_m: float
    transfer_aversion_score: float
    reliability_pref: float

    model_config = {"from_attributes": True}


@router.get("/me", response_model=PreferenceRead)
def read_my_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preference = db.get(Preference, current_user.id)
    return PreferenceRead(
        walking_tolerance_m=preference.walking_tolerance_m,
        transfer_aversion_score=preference.transfer_aversion_score,
        reliability_pref=current_user.reliability_pref,
    )


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
    return PreferenceRead(
        walking_tolerance_m=preference.walking_tolerance_m,
        transfer_aversion_score=preference.transfer_aversion_score,
        reliability_pref=current_user.reliability_pref,
    )
