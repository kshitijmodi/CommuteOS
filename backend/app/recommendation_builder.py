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
from .llm_phrasing import phrase_comparison
from .models import Trip, User
from .transit import lirr, mta, njt_bus, njt_rail, path


@dataclass(frozen=True)
class CandidateSpec:
    """One route/station to fetch live arrivals for and compare - the
    same shape as the API's CandidateRequest, kept separate so this module
    doesn't depend on the router's Pydantic models.
    """

    agency: str  # "mta" | "path" | "njt_rail" | "njt_bus" | "lirr"
    label: str
    stop_or_station: str
    route_or_direction: str = ""


def _candidate_spec_for(
    station: str | None, mode: str | None, route_or_direction: str | None
) -> CandidateSpec | None:
    if station is None or mode is None:
        return None
    if mode in ("mta", "path") and not route_or_direction:
        # Known station, but no route/direction ever captured for it (see
        # User.home_route_or_direction's docstring) - can't call MTA/PATH's
        # get_arrivals without one, so this station can't be auto-derived yet.
        return None
    return CandidateSpec(
        agency=mode,
        label=station,
        stop_or_station=station,
        route_or_direction=route_or_direction or "",
    )


def specs_from_home_office(user: User) -> list[CandidateSpec]:
    """Builds candidates from a user's confirmed home/office inference -
    shared by the scheduled notification job and the on-demand
    /recommendations/from-home-office endpoint, so "what counts as a usable
    home/office candidate" can't drift between the two. Returns an empty
    list (not an error) if home/office isn't confirmed or neither station
    resolves to a usable candidate - callers decide how to respond to that.
    """
    if not user.home_office_confirmed:
        return []
    return [
        spec
        for spec in (
            _candidate_spec_for(user.home_station, user.home_mode, user.home_route_or_direction),
            _candidate_spec_for(
                user.office_station, user.office_mode, user.office_route_or_direction
            ),
        )
        if spec is not None
    ]


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
        elif spec.agency == "lirr":
            result = await lirr.get_arrivals(spec.stop_or_station)
        else:
            result = await njt_bus.get_arrivals(spec.stop_or_station)
        candidates.append(RouteCandidate(mode=spec.agency, label=spec.label, arrivals=result))
    return candidates


async def build_recommendation(
    db: Session, user: User, specs: list[CandidateSpec]
) -> tuple[RankedRoute, list[RankedRoute], str, Trip] | None:
    """Fetches arrivals, ranks them by the user's reliability_pref, phrases
    the winner (explaining the tradeoff against any real alternatives, see
    phrase_comparison), and logs it as a Trip (same trust-preserving
    pattern as POST /recommendations - see that router's docstring).
    Returns None if no candidate has any live arrivals to rank. Does NOT
    commit - the caller decides transaction boundaries (the API commits
    per-request; the notification job commits once per user processed).
    """
    candidates = await fetch_candidates(specs)
    ranked = rank_routes(candidates, reliability_pref=user.reliability_pref, now=datetime.now(timezone.utc))
    if not ranked:
        return None

    best, alternatives = ranked[0], ranked[1:]
    message = phrase_comparison(best, alternatives)

    trip = Trip(
        user_id=user.id,
        start_time=datetime.now(timezone.utc),
        mode=best.mode,
        origin_stop=best.label,
        predicted_arrival=best.predicted_arrival,
    )
    db.add(trip)
    db.flush()

    return best, alternatives, message, trip
