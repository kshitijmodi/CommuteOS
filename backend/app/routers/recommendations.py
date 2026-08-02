from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.deps import get_current_user
from ..decision_engine import RouteCandidate, rank_routes
from ..llm_phrasing import phrase_recommendation
from ..models import Preference, Trip, User
from ..transit import mta, njt_bus, njt_rail, path

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


class CandidateRequest(BaseModel):
    """One option to compare - the client already knows these from its own
    station data (see lib/transit/ in the Flutter app); the decision engine
    doesn't discover routes itself, see decision_engine.py's docstring.
    """

    agency: Literal["mta", "path", "njt_rail", "njt_bus"]
    label: str
    # MTA: GTFS stop_id (e.g. "R20N") + route_id (e.g. "N").
    # PATH: station code (e.g. "JSQ") + direction ("ToNY"/"ToNJ").
    # NJT rail/bus: station/stop_id + route_or_direction unused (both
    # return every line at the stop in one call; there's no separate
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

    route_candidates = []
    for candidate in payload.candidates:
        if candidate.agency == "mta":
            result = await mta.get_arrivals(
                candidate.stop_or_station, candidate.route_or_direction
            )
        elif candidate.agency == "path":
            result = await path.get_arrivals(
                candidate.stop_or_station, candidate.route_or_direction
            )
        elif candidate.agency == "njt_rail":
            result = await njt_rail.get_arrivals(candidate.stop_or_station)
        else:
            result = await njt_bus.get_arrivals(candidate.stop_or_station)
        route_candidates.append(
            RouteCandidate(
                mode=candidate.agency, label=candidate.label, arrivals=result
            )
        )

    preference = db.get(Preference, current_user.id)
    ranked = rank_routes(
        route_candidates,
        reliability_pref=current_user.reliability_pref,
        now=datetime.now(timezone.utc),
    )

    if not ranked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live arrivals found for any candidate route",
        )

    best = ranked[0]
    message = phrase_recommendation(best)

    # Log this recommendation as a trip so its accuracy can be checked
    # later (was_recommendation_followed / actual_arrival, per the PRD's
    # trust-preserving design) - origin_stop records which candidate won.
    trip = Trip(
        user_id=current_user.id,
        start_time=datetime.now(timezone.utc),
        mode=best.mode,
        origin_stop=best.label,
        predicted_arrival=best.predicted_arrival,
    )
    db.add(trip)
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
