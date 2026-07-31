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


def _to_response(user: User) -> HomeOfficeRead:
    return HomeOfficeRead(
        home_station=user.home_station,
        office_station=user.office_station,
        confirmed=user.home_office_confirmed,
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
