from datetime import datetime, timedelta, timezone

from app.decision_engine import RankedRoute
from app.llm_phrasing import (
    _template_comparison_phrase,
    _template_phrase,
    _template_schedule_phrase,
    phrase_comparison,
    phrase_recommendation,
    phrase_schedule_notification,
)
from app.schedule_engine import DisruptionAssessment, DisruptionSeverity


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


def test_schedule_phrase_on_time_cites_real_predicted_arrival():
    assessment = DisruptionAssessment(severity=DisruptionSeverity.ON_TIME, delay_minutes=1.5)
    live = datetime(2026, 1, 1, 8, 10, tzinfo=timezone.utc)

    text = _template_schedule_phrase(assessment, "R20N", live, substitute=None)

    assert "on schedule" in text
    assert "8:10" in text


def test_schedule_phrase_delayed_cites_the_real_delay_minutes_number():
    assessment = DisruptionAssessment(severity=DisruptionSeverity.DELAYED, delay_minutes=15.4)
    live = datetime(2026, 1, 1, 8, 25, tzinfo=timezone.utc)

    text = _template_schedule_phrase(assessment, "R20N", live, substitute=None)

    assert "15" in text
    assert "R20N" in text


def test_schedule_phrase_no_live_data_with_a_substitute():
    assessment = DisruptionAssessment(severity=DisruptionSeverity.NO_LIVE_DATA, delay_minutes=None)
    substitute = _route(mode="mta", label="N train", minutes_from_now=10)

    text = _template_schedule_phrase(assessment, "R20N", None, substitute=substitute)

    assert "isn't showing live data" in text
    assert "N train" in text


def test_schedule_phrase_no_live_data_with_no_substitute_either():
    assessment = DisruptionAssessment(severity=DisruptionSeverity.NO_LIVE_DATA, delay_minutes=None)

    text = _template_schedule_phrase(assessment, "R20N", None, substitute=None)

    assert "isn't showing live data" in text


def test_phrase_schedule_notification_falls_back_to_template_when_no_api_key(monkeypatch):
    monkeypatch.setattr("app.llm_phrasing.settings.groq_api_key", None)
    assessment = DisruptionAssessment(severity=DisruptionSeverity.ON_TIME, delay_minutes=1.0)
    live = datetime(2026, 1, 1, 8, 10, tzinfo=timezone.utc)

    text = phrase_schedule_notification(assessment, "R20N", live)

    assert "R20N" in text
    assert "8:10" in text
