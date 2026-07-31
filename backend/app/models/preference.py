import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..core.database import Base


class Preference(Base):
    """Learned preference scores for a user, recomputed nightly from Trip
    history by a batch job (not live inference) - per the PRD, this keeps
    the "learning" transparent and debuggable and keeps AI cost near-zero
    since Phase 2 has no LLM in this loop at all.

    One row per user (not a history table) - `updated_at` shows when it was
    last recomputed.
    """

    __tablename__ = "preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), primary_key=True
    )
    walking_tolerance_m: Mapped[float] = mapped_column(Float, default=400.0)
    transfer_aversion_score: Mapped[float] = mapped_column(Float, default=0.5)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
