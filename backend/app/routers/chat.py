import uuid

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
    # The caller's real device coordinates, sent only when the client has
    # real location permission AND the question is worth including them
    # for (see lib/chat/chat_repository.dart) - optional, since most
    # questions have nothing to do with location and most callers won't
    # have granted the permission at all. Both must be present together
    # for either to be used; a single stray one is ignored the same as
    # neither being sent.
    lat: float | None = None
    lng: float | None = None
    # A real conversation id, client-generated once and persisted
    # on-device (see lib/chat/chat_repository.dart) - optional, since a
    # caller with no session id (an old client, or one that intentionally
    # wants a fresh single-turn question) still gets a real answer, just
    # with no conversation memory. See chat_ai.answer_question's
    # session_id docs for what this actually unlocks.
    session_id: uuid.UUID | None = None


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
        lat=payload.lat,
        lng=payload.lng,
        session_id=payload.session_id,
    )
    return ChatResponse(
        answer=result.text,
        station_name=result.station.name if result.station else None,
        agency=result.station.agency if result.station else None,
    )
