from datetime import datetime, timedelta, timezone

import pytest

from app.chat_ai import answer_question
from app.transit.models import Arrival, ArrivalsResult


@pytest.fixture(autouse=True)
def no_llm_key(monkeypatch):
    # Deterministic-template path only, matching test_llm_phrasing.py's
    # pattern - keeps assertions stable regardless of a real Groq key
    # being configured on this machine.
    monkeypatch.setattr("app.chat_ai.settings.groq_api_key", None)


@pytest.fixture(autouse=True)
def mock_transit_fetchers(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_mta(stop_id, route_id):
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=7))],
            is_live=True,
        )

    async def fake_path(station_code, direction):
        return ArrivalsResult(
            arrivals=[Arrival(route_label="PATH", arrival_time=now + timedelta(minutes=12))],
            is_live=True,
        )

    async def fake_njt_rail(station_code):
        return ArrivalsResult(arrivals=[], is_live=True)

    monkeypatch.setattr("app.chat_ai.mta.get_arrivals", fake_mta)
    monkeypatch.setattr("app.chat_ai.path.get_arrivals", fake_path)
    monkeypatch.setattr("app.chat_ai.njt_rail.get_arrivals", fake_njt_rail)


@pytest.mark.asyncio
async def test_out_of_scope_question_is_refused_plainly():
    result = await answer_question("how much does a fare cost?")

    assert "don't have that information" in result.text
    assert result.station is None


@pytest.mark.asyncio
async def test_no_match_question_asks_for_clarification():
    result = await answer_question("what about zzz not a real place")

    assert "couldn't find a station" in result.text.lower()
    assert result.station is None


@pytest.mark.asyncio
async def test_exact_station_match_returns_real_arrival_data():
    # "Grove Street" is PATH-only in the index (no NJT rail/MTA station of
    # that exact name), so it's a genuine unambiguous exact match - unlike
    # "Hoboken", which exactly matches both a PATH and an NJT rail station
    # and must stay ambiguous (see the test below).
    result = await answer_question("Grove Street")

    assert result.station is not None
    assert result.station.agency == "path"
    assert "min" in result.text


@pytest.mark.asyncio
async def test_ambiguous_query_lists_real_options_without_picking_one():
    # "23 St" is a genuine same-name collision between several distinct,
    # unconnected real MTA stations (see OPEN_QUESTIONS.md's "23 St"
    # entry) - none of them is a more "correct" pick than another, so
    # this must surface real options rather than silently choosing one.
    result = await answer_question("23 St")

    assert result.station is None
    assert "23 St" in result.text or "did you mean" in result.text.lower()


@pytest.mark.asyncio
async def test_same_name_different_agency_also_stays_ambiguous():
    # "Hoboken" exactly matches both a real PATH station and a real NJT
    # rail station - genuinely different agencies serving the same named
    # place. Silently picking one would answer a different question than
    # the user asked half the time, so this must ask too, not guess PATH.
    result = await answer_question("Hoboken")

    assert result.station is None


@pytest.mark.asyncio
async def test_no_arrivals_found_is_stated_plainly_not_invented():
    result = await answer_question("Grove Street")

    assert result.text


@pytest.mark.asyncio
async def test_falls_back_to_template_when_no_api_key():
    result = await answer_question("Grove Street")

    assert "min" in result.text
