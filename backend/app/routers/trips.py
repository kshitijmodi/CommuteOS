from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import Trip, User

router = APIRouter(prefix="/trips", tags=["trips"])


class TripCreate(BaseModel):
    start_time: datetime
    mode: str
    origin_stop: str
    # Optional: the app currently only knows which station the user
    # viewed, not their destination - see the Trip model's docstring.
    dest_stop: str | None = None


class TripRead(BaseModel):
    id: str
    start_time: datetime
    mode: str
    origin_stop: str
    dest_stop: str | None

    model_config = {"from_attributes": True}


@router.post("", response_model=TripRead, status_code=status.HTTP_201_CREATED)
def create_trip(
    payload: TripCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Records a trip data point for the current user.

    Per the PRD, this is the raw signal the (not-yet-built) nightly batch
    job reads to infer home/office location, typical departure time,
    walking tolerance, and transfer aversion - the app calls this whenever
    the user opens a station's arrivals screen while logged in, not on any
    explicit "start my commute" action, so the data reflects real passive
    usage.
    """
    trip = Trip(
        user_id=current_user.id,
        start_time=payload.start_time,
        mode=payload.mode,
        origin_stop=payload.origin_stop,
        dest_stop=payload.dest_stop,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return TripRead(
        id=str(trip.id),
        start_time=trip.start_time,
        mode=trip.mode,
        origin_stop=trip.origin_stop,
        dest_stop=trip.dest_stop,
    )
