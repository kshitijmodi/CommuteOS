import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, String
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

    # Which agency each station code belongs to (e.g. "mta", "njt_rail") -
    # a bare station code alone is ambiguous across agencies (MTA and NJT
    # bus in particular can both use plain numeric-looking IDs), and the
    # recommendation engine needs to know which live-arrivals API to call.
    # Sourced from the same Trip.mode value the station code itself came
    # from - see home_office_engine.py.
    home_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    office_mode: Mapped[str | None] = mapped_column(String, nullable=True)

    # MTA route ID / PATH direction for the inferred station, when the
    # agency needs one to fetch arrivals (NJT rail/bus don't - a station
    # code alone is enough there). Null if the winning trips predate
    # Trip.route_or_direction existing, or if the agency doesn't need one -
    # a null here for an MTA/PATH station means "can't auto-recommend yet,"
    # not "recommend with no route filter."
    home_route_or_direction: Mapped[str | None] = mapped_column(String, nullable=True)
    office_route_or_direction: Mapped[str | None] = mapped_column(
        String, nullable=True
    )

    # Set by the mobile app once it registers for push notifications (see
    # lib/account/push_registration.dart). Null until the user has opted
    # into proactive notifications - the scheduled commute-notification job
    # (jobs/send_commute_notifications.py) skips any user without one.
    fcm_token: Mapped[str | None] = mapped_column(String, nullable=True)

    # "Arrive on time" (0.0) vs "arrive fastest" (1.0) - the one explicit
    # onboarding input the PRD calls out, since this tradeoff isn't reliably
    # observable from behavior alone. Defaults to neutral until set.
    reliability_pref: Mapped[float] = mapped_column(Float, default=0.5)

    # The UTC calendar date Schedule AI last sent this user a commute
    # notification - see schedule_engine.py. The job now runs hourly
    # (rather than once daily at a fixed time), so this is what prevents
    # notifying the same user more than once per day if their usual
    # departure window happens to span more than one hourly run. A plain
    # Date, not DateTime - only "which day," never a specific time, is
    # tracked here.
    last_commute_notification_date: Mapped[date | None] = mapped_column(
        Date, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
