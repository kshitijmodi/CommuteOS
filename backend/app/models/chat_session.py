import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..core.database import Base


class ChatSession(Base):
    """A real multi-turn conversation, so Chat AI can resolve a follow-up
    question ("what about the other direction", "what about that
    station") against what was actually asked and answered before it -
    fixing a real gap found live: every question used to be answered with
    zero memory of the conversation so far, by design, which read to
    users as "not maintaining context" (a fair complaint - the app never
    told them it was single-turn).

    The session id is CLIENT-generated (a random UUID minted once and
    persisted on-device - see lib/chat/chat_repository.dart) and sent with
    every POST /chat call, not server-issued - this is what lets an
    anonymous (logged-out) caller have real multi-turn memory too, same as
    the rest of this app's "browsing never needs an account" posture.
    [user_id] is attached opportunistically when the caller happens to be
    logged in (same optional-auth pattern as POST /chat itself), purely
    for potential future per-user history features - nothing today reads
    it back out by user_id rather than session_id.
    """

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ChatMessage(Base):
    """One real turn (either side) in a ChatSession, in the order they
    actually happened (created_at + insertion order) - the literal
    transcript used to give the LLM real conversation history, and to
    resolve a station-less follow-up against the last station actually
    discussed (see chat_ai.py's _last_mentioned_station).
    """

    __tablename__ = "chat_messages"

    # The real, DB-assigned autoincrementing primary key - purely to
    # order a session's turns correctly. created_at alone isn't reliable
    # for this: two turns saved in the same request (the user's question
    # and the assistant's answer, see _save_turn) can land on the exact
    # same timestamp depending on the database's clock resolution. A
    # plain autoincrementing integer PK (rather than a UUID like every
    # other model's id) is deliberate here - it's the one column in this
    # table whose entire job is real, portable ordering (works
    # identically on SQLite in tests and Postgres in production, unlike a
    # standalone SEQUENCE, which SQLite doesn't support at all), never
    # exposed outside this module as an external identifier. Plain
    # Integer, not BigInteger - SQLite's autoincrement-on-insert shortcut
    # only kicks in for an exact "INTEGER PRIMARY KEY" column type; a
    # bigint-typed PK silently breaks that and forces id to be supplied
    # manually, which chat_ai.py never does.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text)
    # The real (agency, code) the assistant's turn resolved to, if any -
    # null for a user turn, and null for an assistant turn that didn't
    # land on one real station (out-of-scope, no-match, ambiguous). This
    # is what a later station-less follow-up question falls back to -
    # never a guess synthesized from the message text itself.
    station_agency: Mapped[str | None] = mapped_column(String, nullable=True)
    station_code: Mapped[str | None] = mapped_column(String, nullable=True)
    # The real, distinct headsigns (destinations) this assistant turn's
    # arrivals actually showed, comma-joined - e.g. "33rd Street,World
    # Trade Center" (see chat_ai.py's _answer_direction_toggle, added
    # 2026-08-08 after "what about the other direction" was found
    # hallucinating an answer, since nothing tracked which real
    # destinations were actually shown last). Null for a user turn, an
    # answer with no headsign data at all (MTA/other agencies never
    # report one), or any non-arrivals answer - never guessed.
    shown_headsigns: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
