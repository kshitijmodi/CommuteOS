import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..core.database import Base


class Trip(Base):
    """One recorded trip a user took (or was shown as an option for).

    Populated by the mobile app as the user actually commutes - this table
    is the raw signal Phase 2's nightly batch job reads to compute
    `Preferences` from. Per the PRD, this is deliberately structured/
    low-cardinality data (a handful of columns), not something needing a
    vector store.
    """

    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)

    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mode: Mapped[str] = mapped_column(String)  # e.g. "mta", "path", "njt"
    origin_stop: Mapped[str] = mapped_column(String)

    # Nullable: the app currently only knows which station the user viewed,
    # not where they were headed - real destination capture needs a later
    # route-planning feature. Null here means "unknown", not "same as
    # origin" - never fill this with a guessed/duplicated value.
    dest_stop: Mapped[str | None] = mapped_column(String, nullable=True)

    predicted_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    actual_arrival: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Null until Phase 3 actually issues recommendations to follow/ignore.
    was_recommendation_followed: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
