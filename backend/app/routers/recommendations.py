from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User
from ..recommendation_builder import CandidateSpec, build_recommendation, specs_from_home_office

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class CandidateRequest(BaseModel):
    """One option to compare - the client already knows these from its own
    station data (see lib/transit/ in the Flutter app); the decision engine
    doesn't discover routes itself, see decision_engine.py's docstring.
    """

    agency: Literal["mta", "path", "njt_rail", "njt_bus", "lirr"]
    label: str
    # MTA: GTFS stop_id (e.g. "R20N") + route_id (e.g. "N").
    # PATH: station code (e.g. "JSQ") + direction ("ToNY"/"ToNJ").
    # NJT rail/bus/LIRR: station/stop code + route_or_direction unused (all
    # three return every line at the stop in one call; there's no separate
    # direction/route filter the way MTA/PATH need).
    stop_or_station: str
    route_or_direction: str = ""


class RecommendationRequest(BaseModel):
    candidates: list[CandidateRequest]


class RecommendationResponse(BaseModel):
    mode: str
    label: str
    predicted_arrival: datetime
    confidence: float
    is_live: bool
    message: str
    trip_id: str


@router.post("", response_model=RecommendationResponse)
async def get_recommendation(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.candidates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one candidate route is required",
        )

    specs = [
        CandidateSpec(
            agency=c.agency,
            label=c.label,
            stop_or_station=c.stop_or_station,
            route_or_direction=c.route_or_direction,
        )
        for c in payload.candidates
    ]
    outcome = await build_recommendation(db, current_user, specs)

    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live arrivals found for any candidate route",
        )

    best, message, trip = outcome
    db.commit()
    db.refresh(trip)

    return RecommendationResponse(
        mode=best.mode,
        label=best.label,
        predicted_arrival=best.predicted_arrival,
        confidence=best.confidence,
        is_live=best.is_live,
        message=message,
        trip_id=str(trip.id),
    )


@router.get("/from-home-office", response_model=RecommendationResponse)
async def get_recommendation_from_home_office(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Same engine as POST /recommendations, but with candidates derived
    automatically from the user's confirmed home/office inference instead
    of the client passing them explicitly - reuses exactly the same
    eligibility rule the scheduled notification job uses (see
    recommendation_builder.specs_from_home_office), so "who counts as
    ready for auto-recommendations" can't drift between the two. 404s
    (rather than returning an empty/default result) when the user isn't
    eligible yet, so the client can fall back to manual favorite-picking.
    """
    specs = specs_from_home_office(current_user)
    if not specs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Home/office isn't confirmed yet, or isn't resolvable to a candidate route",
        )

    outcome = await build_recommendation(db, current_user, specs)

    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live arrivals found for your home/office stations",
        )

    best, message, trip = outcome
    db.commit()
    db.refresh(trip)

    return RecommendationResponse(
        mode=best.mode,
        label=best.label,
        predicted_arrival=best.predicted_arrival,
        confidence=best.confidence,
        is_live=best.is_live,
        message=message,
        trip_id=str(trip.id),
    )
