"""Phase 3 decision engine: deterministic, rules/weighted-scoring based -
explicitly NOT an LLM, per the PRD. The LLM's only job (see
llm_phrasing.py) is turning this module's structured output into a
sentence; it never sees raw trip history or makes the actual decision.

Score formula (per the PRD): a route's score = predicted_arrival_time -
(reliability_weight x recent_delay_variance). Lower score = better (sooner
+ more reliable, weighted by the user's own reliability preference).

This module only knows how to score a fixed set of candidate options it's
given - it doesn't discover routes or do trip planning. That's a
deliberate scope cut: real route-finding (given any two stations, what
paths exist) is a much bigger feature than a weekend rapid-build phase 3
can responsibly own, and the PRD's own examples only ever compare a
small, already-known set of alternatives (e.g. "your usual PATH vs NJ
Transit").
"""

from dataclasses import dataclass
from datetime import datetime

from .transit.models import ArrivalsResult


@dataclass(frozen=True)
class RouteCandidate:
    """One way to make a trip, e.g. "PATH from JSQ" vs "NJ Transit from
    Newark" - whatever the caller already knows are the live alternatives
    for this user's usual commute.
    """

    mode: str
    label: str
    arrivals: ArrivalsResult


@dataclass(frozen=True)
class RankedRoute:
    mode: str
    label: str
    depart_by: datetime
    predicted_arrival: datetime
    confidence: float
    score: float
    is_live: bool


def rank_routes(
    candidates: list[RouteCandidate],
    reliability_pref: float,
    now: datetime,
) -> list[RankedRoute]:
    """Ranks candidates soonest-and-most-reliable-first, weighted by the
    user's reliability_pref (0.0 = "arrive on time" i.e. favor reliability,
    1.0 = "arrive fastest" i.e. favor speed - per the PRD's onboarding
    slider framing).

    Each candidate's next arrival is used as its predicted_arrival. Recent
    delay variance isn't computable yet (would need historical
    predicted-vs-actual deltas across many past trips per route, which
    Phase 2's trip history doesn't yet capture at the volume/shape needed)
    - so reliability_weight currently penalizes non-live (degraded/stale)
    data instead, as a proxy for "how much can I trust this number." This
    is a real scope cut, not a hidden shortcut - documented here and in
    OPEN_QUESTIONS.md so it's not mistaken for the PRD's full formula.
    """
    ranked = []
    for candidate in candidates:
        if not candidate.arrivals.arrivals:
            continue

        next_arrival = candidate.arrivals.arrivals[0]
        seconds_until = (next_arrival.arrival_time - now).total_seconds()

        # Confidence is a simple, explainable stand-in for "recent delay
        # variance": live data is trusted more than stale/degraded data.
        # Never overstate this as more than it is - see PRD trust section.
        confidence = 0.9 if candidate.arrivals.is_live else 0.4

        # reliability_pref near 0 -> penalize low confidence more heavily
        # (user cares about reliability); near 1 -> barely penalize it
        # (user just wants the fastest option regardless of confidence).
        reliability_weight = 1.0 - reliability_pref
        unreliability_penalty = (1.0 - confidence) * reliability_weight * 600
        score = seconds_until + unreliability_penalty

        ranked.append(
            RankedRoute(
                mode=candidate.mode,
                label=candidate.label,
                depart_by=now,
                predicted_arrival=next_arrival.arrival_time,
                confidence=confidence,
                score=score,
                is_live=candidate.arrivals.is_live,
            )
        )

    ranked.sort(key=lambda r: r.score)
    return ranked
