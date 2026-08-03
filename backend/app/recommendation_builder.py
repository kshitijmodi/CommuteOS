"""Shared logic for building a phrased recommendation from a set of
candidate routes - used by both POST /recommendations (user-picked
candidates from the Flutter app) and the scheduled commute-notification
job (candidates auto-derived from a user's inferred home/office station).
Factored out so both call sites score/phrase/log identically rather than
maintaining two copies of the same pipeline.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .decision_engine import RankedRoute, RouteCandidate, rank_routes
from .llm_phrasing import phrase_recommendation
from .models import Trip, User
from .transit import mta, njt_bus, njt_rail, path


@dataclass(frozen=True)
class CandidateSpec:
    """One route/station to fetch live arrivals for and compare - the
    same shape as the API's CandidateRequest, kept separate so this module
    doesn't depend on the router's Pydantic models.
    """

    agency: str  # "mta" | "path" | "njt_rail" | "njt_bus"
    label: str
    stop_or_station: str
    route_or_direction: str = ""


async def fetch_candidates(specs: list[CandidateSpec]) -> list[RouteCandidate]:
    """Fetches live arrivals for each spec and returns them as scoreable
    RouteCandidates. A spec whose agency's fetch fails or returns no
    arrivals is naturally excluded downstream by rank_routes - errors
    aren't swallowed here, they propagate (matching /recommendations'
    existing behavior of letting a single bad candidate fail loudly rather
    than silently dropping it).
    """
    candidates = []
    for spec in specs:
        if spec.agency == "mta":
            result = await mta.get_arrivals(spec.stop_or_station, spec.route_or_direction)
        elif spec.agency == "path":
            result = await path.get_arrivals(spec.stop_or_station, spec.route_or_direction)
        elif spec.agency == "njt_rail":
            result = await njt_rail.get_arrivals(spec.stop_or_station)
        else:
            result = await njt_bus.get_arrivals(spec.stop_or_station)
        candidates.append(RouteCandidate(mode=spec.agency, label=spec.label, arrivals=result))
    return candidates


async def build_recommendation(
    db: Session, user: User, specs: list[CandidateSpec]
) -> tuple[RankedRoute, str, Trip] | None:
    """Fetches arrivals, ranks them by the user's reliability_pref, phrases
    the winner, and logs it as a Trip (same trust-preserving pattern as
    POST /recommendations - see that router's docstring). Returns None if
    no candidate has any live arrivals to rank. Does NOT commit - the
    caller decides transaction boundaries (the API commits per-request;
    the notification job commits once per user processed).
    """
    candidates = await fetch_candidates(specs)
    ranked = rank_routes(candidates, reliability_pref=user.reliability_pref, now=datetime.now(timezone.utc))
    if not ranked:
        return None

    best = ranked[0]
    message = phrase_recommendation(best)

    trip = Trip(
        user_id=user.id,
        start_time=datetime.now(timezone.utc),
        mode=best.mode,
        origin_stop=best.label,
        predicted_arrival=best.predicted_arrival,
    )
    db.add(trip)
    db.flush()

    return best, message, trip
