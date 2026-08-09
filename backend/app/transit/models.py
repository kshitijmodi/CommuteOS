"""Backend-side transit types, mirroring lib/transit/transit_models.dart -
kept intentionally simpler since the backend only needs enough to score
routes, not render a full UI. If these two ever need to share more logic
than "same shape, different language," that's a signal to reconsider the
duplication, not before.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Arrival:
    route_label: str
    arrival_time: datetime
    # The real destination this specific arrival is headed toward, when
    # the source feed reports one (PATH's feed carries a real "headSign"
    # per arrival, e.g. "World Trade Center" or "33rd Street" - see
    # transit/path.py; added 2026-08-08 after chat_ai.py was found
    # hallucinating an answer to "what about the other direction"
    # because this field never existed and every PATH arrival looked
    # identical once fetched). None for agencies/feeds that don't report
    # a real per-arrival destination (MTA's GTFS-RT never includes a
    # headsign at all) - never guessed or defaulted to a placeholder.
    headsign: str | None = None

    @property
    def minutes_until(self) -> float:
        from datetime import timezone

        now = datetime.now(timezone.utc)
        arrival = self.arrival_time
        if arrival.tzinfo is None:
            arrival = arrival.replace(tzinfo=timezone.utc)
        return (arrival - now).total_seconds() / 60


@dataclass(frozen=True)
class ArrivalsResult:
    arrivals: list[Arrival]
    is_live: bool
