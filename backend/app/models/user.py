import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)

    # Per the PRD's Phase 2 schema, these were meant to be lat/lng - but
    # Trip only records a station code (origin_stop), not GPS coordinates,
    # and syncing a station->coordinate lookup to the backend (PATH doesn't
    # even have consistent coordinates) was a scope cut for now. Left
    # unused rather than repurposed, so a future real lat/lng
    # implementation isn't blocked by a schema mismatch.
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    office_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    office_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # What's actually inferred today: station codes, not coordinates - see
    # home_office_engine.py. Null until ~5+ trips exist to infer from;
    # *_confirmed tracks the PRD's "confirmed once via a simple prompt"
    # step, since an unconfirmed inference shouldn't be treated as
    # authoritative for e.g. auto-scheduling notifications.
    home_station: Mapped[str | None] = mapped_column(String, nullable=True)
    office_station: Mapped[str | None] = mapped_column(String, nullable=True)
    home_office_confirmed: Mapped[bool] = mapped_column(default=False)

    # "Arrive on time" (0.0) vs "arrive fastest" (1.0) - the one explicit
    # onboarding input the PRD calls out, since this tradeoff isn't reliably
    # observable from behavior alone. Defaults to neutral until set.
    reliability_pref: Mapped[float] = mapped_column(Float, default=0.5)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
