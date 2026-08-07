from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..behavior_engine import (
    direction_choices_for_user,
    feed_accuracy_for_user,
    timing_buffers_for_user,
)
from ..core.database import get_db
from ..core.deps import get_current_user
from ..models import User

router = APIRouter(prefix="/behavior", tags=["behavior"])


class FeedAccuracyOut(BaseModel):
    mode: str
    origin_stop: str
    time_slot: int
    sample_count: int
    average_error_minutes: float

    model_config = {"from_attributes": True}


class DirectionChoiceOut(BaseModel):
    origin_stop: str
    time_slot: int
    sample_count: int
    most_common_route_or_direction: str
    confidence: float

    model_config = {"from_attributes": True}


class TimingBufferOut(BaseModel):
    origin_stop: str
    time_slot: int
    sample_count: int
    average_buffer_minutes: float

    model_config = {"from_attributes": True}


class BehaviorSummary(BaseModel):
    """Read-only view into what Behavior AI has learned so far - exposed
    mainly so the app can show "here's what CommuteOS has picked up on you"
    (same trust-preserving spirit as GET /preferences/me), and so Commute/
    Schedule/Chat AI have a single endpoint to sanity-check against during
    development. The actual read path those features use at request time is
    behavior_engine.predict_direction, called directly - not this endpoint.
    """

    feed_accuracy: list[FeedAccuracyOut]
    direction_choices: list[DirectionChoiceOut]
    timing_buffers: list[TimingBufferOut]


@router.get("/me", response_model=BehaviorSummary)
def read_my_behavior(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BehaviorSummary(
        feed_accuracy=feed_accuracy_for_user(db, current_user.id),
        direction_choices=direction_choices_for_user(db, current_user.id),
        timing_buffers=timing_buffers_for_user(db, current_user.id),
    )
