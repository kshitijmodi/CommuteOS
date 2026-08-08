from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..chat_ai import answer_question
from ..core.database import get_db
from ..core.deps import get_current_user_optional
from ..models import User

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    station_name: str | None = None
    agency: str | None = None


@router.post("", response_model=ChatResponse)
async def ask_chat(
    payload: ChatRequest,
    current_user: User | None = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    """One endpoint, both of Chat AI's tiers - auth is optional, not
    required, matching this app's existing pattern that browsing/asking
    about transit data never needs an account. A logged-in caller asking
    a personal-sounding question ("what do I usually take from here")
    gets the personalized tier (see chat_ai.answer_question); anyone
    else, or a personal question that comes back with nothing to
    personalize, gets the stateless tier - never an error either way.
    Deliberately still stateless in the conversational sense: no message
    history is stored or read here, each question is answered
    independently, per the PRD's own framing.
    """
    result = await answer_question(
        payload.question,
        db=db,
        user_id=current_user.id if current_user else None,
    )
    return ChatResponse(
        answer=result.text,
        station_name=result.station.name if result.station else None,
        agency=result.station.agency if result.station else None,
    )
