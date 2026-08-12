from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..home_office_engine import infer_home_and_office
from ..models import User

router = APIRouter(prefix="/home-office", tags=["home-office"])


class HomeOfficeRead(BaseModel):
    home_station: str | None
    office_station: str | None
    confirmed: bool
    # Which agency each station code belongs to - added 2026-08-12 so the
    # client can resolve a bare code (e.g. "JSQ") to a real station (with
    # real lat/lng) for background geofencing (see
    # lib/behavior/station_geofence_service.dart). Was already tracked on
    # User (home_mode/office_mode) but never exposed here before - a bare
    # station code alone is ambiguous across agencies (see User.home_mode's
    # own docstring), so this endpoint was previously unusable for anything
    # that needs to know WHICH agency's station data to look the code up
    # against.
    home_mode: str | None
    office_mode: str | None


def _to_response(user: User) -> HomeOfficeRead:
    return HomeOfficeRead(
        home_station=user.home_station,
        office_station=user.office_station,
        confirmed=user.home_office_confirmed,
        home_mode=user.home_mode,
        office_mode=user.office_mode,
    )


@router.get("/me", response_model=HomeOfficeRead)
def read_my_home_office(current_user: User = Depends(get_current_user)):
    return _to_response(current_user)


@router.post("/me/infer", response_model=HomeOfficeRead)
def infer_my_home_office(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually triggers inference from current trip history - like
    /preferences/me/recompute, this stands in for the nightly batch job
    for now (see home_office_engine.py's module docstring).
    """
    user = infer_home_and_office(db, current_user.id)
    db.commit()
    return _to_response(user)


@router.post("/me/confirm", response_model=HomeOfficeRead)
def confirm_my_home_office(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per the PRD: home/office inference is 'confirmed once via a simple
    prompt' - this is that confirmation. Only meaningful once
    home_station/office_station are actually set; confirming with both
    still null is harmless but pointless.
    """
    current_user.home_office_confirmed = True
    db.commit()
    db.refresh(current_user)
    return _to_response(current_user)
