from fastapi import APIRouter
from pydantic import BaseModel

from ..chat_ai import answer_question

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    station_name: str | None = None
    agency: str | None = None


@router.post("", response_model=ChatResponse)
async def ask_chat(payload: ChatRequest):
    """Chat AI's stateless tier - no auth required, matching this app's
    existing pattern that browsing/asking about transit data never needs
    an account (see recommendations/transit routers). Deliberately
    stateless: no conversation history is stored or read here - the
    personalized tier (reading Behavior AI's history) is a separate,
    not-yet-built endpoint per the PRD's two-tier split.
    """
    result = await answer_question(payload.question)
    return ChatResponse(
        answer=result.text,
        station_name=result.station.name if result.station else None,
        agency=result.station.agency if result.station else None,
    )
