from datetime import datetime, timedelta, timezone

from app.decision_engine import RankedRoute
from app.llm_phrasing import (
    _template_comparison_phrase,
    _template_phrase,
    phrase_comparison,
    phrase_recommendation,
)


def _route(mode="path", label="PATH", confidence=0.9, minutes_from_now=15):
    base = datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc)
    return RankedRoute(
        mode=mode,
        label=label,
        depart_by=base,
        predicted_arrival=base + timedelta(minutes=minutes_from_now),
        confidence=confidence,
        score=900,
        is_live=True,
    )


def test_falls_back_to_template_when_no_api_key(monkeypatch):
    monkeypatch.setattr("app.llm_phrasing.settings.groq_api_key", None)

    result = phrase_recommendation(_route())

    assert "PATH" in result
    assert "8:15" in result


def test_template_hedges_low_confidence():
    text = _template_phrase(_route(confidence=0.3))
    assert "might" in text


def test_template_is_confident_for_high_confidence():
    text = _template_phrase(_route(confidence=0.9))
    assert "should" in text


def test_comparison_falls_back_to_plain_phrasing_with_no_alternatives(monkeypatch):
    monkeypatch.setattr("app.llm_phrasing.settings.groq_api_key", None)

    result = phrase_comparison(_route(), [])

    assert "PATH" in result
    assert "8:15" in result


def test_comparison_falls_back_to_template_when_no_api_key(monkeypatch):
    monkeypatch.setattr("app.llm_phrasing.settings.groq_api_key", None)

    winner = _route(mode="mta", label="N train", minutes_from_now=10)
    runner_up = _route(mode="path", label="PATH", minutes_from_now=15)

    result = phrase_comparison(winner, [runner_up])

    assert "N train" in result
    assert "PATH" in result


def test_template_comparison_cites_speed_when_winner_is_sooner():
    winner = _route(mode="mta", label="N train", minutes_from_now=10)
    runner_up = _route(mode="path", label="PATH", minutes_from_now=15)

    text = _template_comparison_phrase(winner, [runner_up])

    assert "sooner" in text
    assert "PATH" in text


def test_template_comparison_cites_reliability_when_winner_is_slower_but_more_confident():
    # Winner arrives LATER than the alternative but was still ranked first -
    # only possible because it's more reliable (see decision_engine's
    # reliability-weighted scoring) - the phrasing should say so, not claim
    # a speed advantage that isn't real.
    winner = _route(mode="mta", label="N train", confidence=0.9, minutes_from_now=20)
    runner_up = _route(mode="path", label="PATH", confidence=0.4, minutes_from_now=15)

    text = _template_comparison_phrase(winner, [runner_up])

    assert "reliable" in text
    assert "PATH" in text
