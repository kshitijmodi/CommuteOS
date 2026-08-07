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

    # The specific route/direction viewed, e.g. MTA route ID "N" or PATH
    # direction "ToNY" - needed to actually re-fetch live arrivals for this
    # exact station later (e.g. the commute notification job), since a
    # bare origin_stop alone isn't enough for MTA/PATH's get_arrivals(),
    # which both require a route_id/direction parameter (unlike NJT rail/
    # bus, where a station code alone is sufficient). Nullable because
    # historical trips logged before this column existed have no value to
    # backfill it with - never guess one.
    route_or_direction: Mapped[str | None] = mapped_column(String, nullable=True)

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

    # When the user actually started moving toward this trip's station -
    # reported by the client the same way actual_arrival is (see
    # routers/trip_outcomes.py). Feeds Behavior AI's "personal timing
    # buffer" signal (how long before a train's predicted arrival this
    # user actually leaves): buffer = predicted_arrival - left_at. Null
    # for every trip logged before this existed, and for any trip the
    # client never reports it for - never backfilled or guessed.
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
