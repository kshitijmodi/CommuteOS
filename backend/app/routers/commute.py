from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..commute_engine import recommend_for_station
from ..core.database import get_db
from ..core.deps import get_current_user
from ..llm_phrasing import phrase_commute_recommendation
from ..models import User

router = APIRouter(prefix="/commute", tags=["commute"])


class CommuteAlternativeOut(BaseModel):
    mode: str
    label: str
    predicted_arrival: datetime
    confidence: float
    is_live: bool


class CommuteResponse(BaseModel):
    mode: str
    label: str
    predicted_arrival: datetime
    confidence: float
    is_live: bool
    message: str
    usual_route_or_direction: str | None
    differs_from_usual: bool
    alternatives: list[CommuteAlternativeOut] = []


@router.get("/{agency}/{code}", response_model=CommuteResponse)
async def get_commute_recommendation(
    agency: str,
    code: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Commute AI - fired when the client opens a station's arrivals
    screen (see commute_engine.py's module docstring). Requires auth,
    unlike the transit/chat routers, since it reads the user's own
    Behavior AI history (predict_direction) to know their usual pick -
    there's no meaningful "Commute AI for a logged-out user" the way
    there is for plain arrivals browsing or Chat AI's stateless tier.

    404s (never a fabricated result) when the station isn't in the index
    or none of its real candidates have live arrivals right now - the
    client falls back to showing every direction unranked, same as it
    already does before this feature existed, per the PRD's explicit
    Commute AI fallback.
    """
    recommendation = await recommend_for_station(
        db, current_user.id, agency, code, current_user.reliability_pref
    )
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No live arrivals found for this station's real options",
        )

    message = phrase_commute_recommendation(recommendation)
    winner = recommendation.winner

    return CommuteResponse(
        mode=winner.mode,
        label=winner.label,
        predicted_arrival=winner.predicted_arrival,
        confidence=winner.confidence,
        is_live=winner.is_live,
        message=message,
        usual_route_or_direction=recommendation.usual_route_or_direction,
        differs_from_usual=recommendation.differs_from_usual,
        alternatives=[
            CommuteAlternativeOut(
                mode=a.mode,
                label=a.label,
                predicted_arrival=a.predicted_arrival,
                confidence=a.confidence,
                is_live=a.is_live,
            )
            for a in recommendation.alternatives
        ],
    )
