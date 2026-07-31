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
