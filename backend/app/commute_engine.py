"""Commute AI (see PRD Phase 3) - the single, sole owner of "which route/
mode is best right now" for a station the user is actively looking at.
Fires when the user opens a multi-option station's arrivals screen (a
location-triggered, in-app event - not GPS), infers the likely usual
choice from Behavior AI's history at that station/time, and recommends
the fastest/most-reliable REAL option among that station's own real
candidates (its own routes/directions - not a home-vs-office comparison,
which is what recommendation_builder.py's specs_from_home_office already
covers for Schedule AI/the manual recommendation screen).

Deterministic, no LLM in the ranking path. rank_best (below) IS the PRD's
"shared brain" - the literal one function that decides "given known
alternatives, which is best right now" (see the PRD's own wording).
recommend_for_station wraps it with what's specific to Commute AI's own
trigger (deriving a station's own candidate set, comparing the winner
against Behavior AI's inferred usual pick) - but the ranking call itself
is the exact same function Schedule AI's substitute path calls (see
jobs/send_commute_notifications.py) and recommendation_builder.py's
home/office comparison calls, not a parallel copy. Each caller differs
only in which candidates it hands in and how it phrases the result -
never in the ranking logic itself, per the PRD's explicit framing.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .behavior_engine import predict_direction
from .decision_engine import RankedRoute, RouteCandidate, rank_routes
from .recommendation_builder import CandidateSpec, fetch_candidates
from .station_index import station_for


@dataclass(frozen=True)
class CommuteRecommendation:
    winner: RankedRoute
    alternatives: list[RankedRoute]
    # The user's own inferred usual pick at this station/hour (Behavior
    # AI's direction_choice signal), if there's enough history - None
    # when there isn't, which callers must treat as "nothing to compare
    # against," never a guessed default.
    usual_route_or_direction: str | None
    # True only when there's real history AND the winner's
    # route_or_direction differs from it - the actual "take X instead of
    # your usual" moment the PRD describes. False (not None) whenever
    # there's no usual to compare against, since "no known usual" is not
    # itself a disagreement worth flagging.
    differs_from_usual: bool


def candidates_for_station(agency: str, code: str) -> list[CandidateSpec] | None:
    """The station's own real candidate set - every route/direction
    get_arrivals can actually be called with for it. None (never a guess)
    if the station isn't in the index at all; callers must fall back to
    "nothing to recommend" rather than fabricate one. An index hit with an
    empty routes list (NJT rail/bus/LIRR, which need no route/direction)
    still returns a single one-candidate list - there's exactly one real
    "option" at those stations, which is a degenerate but valid case for
    rank_routes to score (nothing to compare it against, but a real
    result all the same).
    """
    station = station_for(agency, code)
    if station is None:
        return None

    if station.routes:
        return [
            CandidateSpec(
                agency=agency,
                label=route,
                stop_or_station=code,
                route_or_direction=route,
            )
            for route in station.routes
        ]
    return [CandidateSpec(agency=agency, label=station.name, stop_or_station=code)]


def rank_best(
    candidates: list[RouteCandidate], reliability_pref: float, now: datetime
) -> list[RankedRoute]:
    """The PRD's "shared brain" - see module docstring. A thin, named
    pass-through to decision_engine.rank_routes rather than callers
    importing rank_routes directly, so every caller (this module,
    Schedule AI's substitute path, recommendation_builder's home/office
    compare) is visibly calling the SAME named entry point Commute AI
    owns, not a coincidentally-identical second copy.
    """
    return rank_routes(candidates, reliability_pref=reliability_pref, now=now)


async def recommend_for_station(
    db: Session, user_id, agency: str, code: str, reliability_pref: float
) -> CommuteRecommendation | None:
    """The one function Commute AI's endpoint calls. Returns None (never
    a guess) when the station isn't in the index, or when none of its
    real candidates have any live arrivals right now - callers must fall
    back to showing every direction unranked in either case, per the
    PRD's explicit Commute AI fallback.
    """
    specs = candidates_for_station(agency, code)
    if specs is None:
        return None

    candidates = await fetch_candidates(specs)
    ranked = rank_best(candidates, reliability_pref=reliability_pref, now=datetime.now(timezone.utc))
    if not ranked:
        return None

    winner, alternatives = ranked[0], ranked[1:]

    usual = predict_direction(db, user_id, code, datetime.now(timezone.utc).hour)
    usual_route_or_direction = usual.most_common_route_or_direction if usual else None
    differs_from_usual = (
        usual_route_or_direction is not None and winner.label != usual_route_or_direction
    )

    return CommuteRecommendation(
        winner=winner,
        alternatives=alternatives,
        usual_route_or_direction=usual_route_or_direction,
        differs_from_usual=differs_from_usual,
    )
