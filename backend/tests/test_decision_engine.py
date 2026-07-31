from datetime import datetime, timedelta, timezone

from app.decision_engine import RouteCandidate, rank_routes
from app.transit.models import Arrival, ArrivalsResult

NOW = datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc)


def _candidate(mode, label, minutes_away, is_live=True):
    return RouteCandidate(
        mode=mode,
        label=label,
        arrivals=ArrivalsResult(
            arrivals=[
                Arrival(
                    route_label=mode,
                    arrival_time=NOW + timedelta(minutes=minutes_away),
                )
            ],
            is_live=is_live,
        ),
    )


def test_sooner_arrival_ranks_first_when_both_live():
    candidates = [
        _candidate("path", "PATH", minutes_away=20),
        _candidate("njt", "NJ Transit", minutes_away=10),
    ]

    ranked = rank_routes(candidates, reliability_pref=0.5, now=NOW)

    assert ranked[0].mode == "njt"
    assert ranked[1].mode == "path"


def test_candidates_with_no_arrivals_are_excluded():
    empty = RouteCandidate(
        mode="mta", label="MTA", arrivals=ArrivalsResult(arrivals=[], is_live=True)
    )
    candidates = [empty, _candidate("path", "PATH", minutes_away=15)]

    ranked = rank_routes(candidates, reliability_pref=0.5, now=NOW)

    assert len(ranked) == 1
    assert ranked[0].mode == "path"


def test_low_reliability_pref_penalizes_stale_data_more():
    # A stale-but-technically-sooner option should lose to a live option
    # when the user strongly prefers reliability (reliability_pref near 0).
    candidates = [
        _candidate("path", "PATH", minutes_away=5, is_live=False),
        _candidate("njt", "NJ Transit", minutes_away=8, is_live=True),
    ]

    ranked = rank_routes(candidates, reliability_pref=0.0, now=NOW)

    assert ranked[0].mode == "njt"


def test_high_reliability_pref_favors_speed_over_confidence():
    # Same two candidates, but a user who just wants the fastest option
    # (reliability_pref near 1) should pick the sooner one even if stale.
    candidates = [
        _candidate("path", "PATH", minutes_away=5, is_live=False),
        _candidate("njt", "NJ Transit", minutes_away=8, is_live=True),
    ]

    ranked = rank_routes(candidates, reliability_pref=1.0, now=NOW)

    assert ranked[0].mode == "path"


def test_confidence_reflects_live_vs_stale():
    candidates = [_candidate("mta", "MTA", minutes_away=5, is_live=False)]

    ranked = rank_routes(candidates, reliability_pref=0.5, now=NOW)

    assert ranked[0].confidence == 0.4
    assert ranked[0].is_live is False


def test_empty_candidate_list_returns_empty_ranking():
    assert rank_routes([], reliability_pref=0.5, now=NOW) == []
