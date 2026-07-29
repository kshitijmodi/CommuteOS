import uuid
from datetime import datetime

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)

    # Per the PRD's Phase 2 schema: home/office are inferred from usage over
    # ~5 trips, confirmed once via a prompt - nullable until that happens.
    home_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    office_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    office_lng: Mapped[float | None] = mapped_column(Float, nullable=True)

    # "Arrive on time" (0.0) vs "arrive fastest" (1.0) - the one explicit
    # onboarding input the PRD calls out, since this tradeoff isn't reliably
    # observable from behavior alone. Defaults to neutral until set.
    reliability_pref: Mapped[float] = mapped_column(Float, default=0.5)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
