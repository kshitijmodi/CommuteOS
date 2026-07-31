import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import Trip, User

router = APIRouter(prefix="/trips", tags=["trips"])


class TripOutcomeUpdate(BaseModel):
    was_recommendation_followed: bool | None = None
    actual_arrival: datetime | None = None


@router.patch("/{trip_id}/outcome")
def report_trip_outcome(
    trip_id: str,
    payload: TripOutcomeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lets the client report what actually happened after a recommendation
    was made - per the PRD's trust-preserving design ("track
    was_recommendation_followed and actual_arrival so the app can honestly
    report its own accuracy over time"). This is what makes the accuracy
    endpoint (GET /trips/accuracy) meaningful rather than just trusting
    the engine's own confidence claims.
    """
    try:
        parsed_id = uuid.UUID(trip_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="trip_id must be a valid UUID",
        )

    trip = db.get(Trip, parsed_id)
    if trip is None or trip.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found"
        )

    if payload.was_recommendation_followed is not None:
        trip.was_recommendation_followed = payload.was_recommendation_followed
    if payload.actual_arrival is not None:
        trip.actual_arrival = payload.actual_arrival

    db.commit()
    return {"status": "updated"}


class AccuracyResponse(BaseModel):
    recommendations_made: int
    recommendations_followed: int
    average_error_minutes: float | None


@router.get("/accuracy", response_model=AccuracyResponse)
def get_recommendation_accuracy(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Per the PRD's exit criteria for Phase 3: recommendation accuracy
    (predicted vs. actual arrival) tracked and visible - this is that
    number, computed honestly from only the trips that have both a
    prediction and a reported actual arrival (others are still pending
    outcome and shouldn't count toward or against accuracy either way).
    """
    trips = (
        db.query(Trip)
        .filter(
            Trip.user_id == current_user.id,
            Trip.predicted_arrival.isnot(None),
        )
        .all()
    )

    followed_count = sum(1 for t in trips if t.was_recommendation_followed)

    errors = [
        abs((t.actual_arrival - t.predicted_arrival).total_seconds()) / 60
        for t in trips
        if t.actual_arrival is not None
    ]
    average_error = sum(errors) / len(errors) if errors else None

    return AccuracyResponse(
        recommendations_made=len(trips),
        recommendations_followed=followed_count,
        average_error_minutes=average_error,
    )
