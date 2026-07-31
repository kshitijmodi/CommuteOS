from datetime import datetime, timezone

from app.decision_engine import RankedRoute
from app.llm_phrasing import _template_phrase, phrase_recommendation


def _route(confidence=0.9):
    return RankedRoute(
        mode="path",
        label="PATH",
        depart_by=datetime(2026, 7, 31, 8, 0, tzinfo=timezone.utc),
        predicted_arrival=datetime(2026, 7, 31, 8, 15, tzinfo=timezone.utc),
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
