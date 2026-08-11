import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.chat_ai import answer_question
from app.core.security import hash_password
from app.models import ChatMessage, ChatSession, Trip, User
from app.transit.models import Arrival, ArrivalsResult


def _make_user(db_session, email="chatpersonal@example.com"):
    user = User(email=email, hashed_password=hash_password("hunter2"))
    db_session.add(user)
    db_session.flush()
    db_session.commit()
    return user


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
        # Different arrival times per route so rank_routes has a
        # deterministic winner (N sooner than W) - the personalized-tier
        # tests below rely on this to prove a real "differs from usual"
        # comparison, not an arbitrary tie-break.
        arrival_minutes = {"N": 5, "W": 10}.get(route_id, 7)
        return ArrivalsResult(
            arrivals=[Arrival(route_label=route_id, arrival_time=now + timedelta(minutes=arrival_minutes))],
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
    # commute_engine.recommend_for_station (the personalized tier's real
    # read path) fetches through recommendation_builder.fetch_candidates,
    # a different module/patch-target than chat_ai's own stateless fetch
    # helpers above - both need mocking for the personalized-tier tests.
    monkeypatch.setattr("app.recommendation_builder.mta.get_arrivals", fake_mta)
    monkeypatch.setattr("app.recommendation_builder.path.get_arrivals", fake_path)


@pytest.mark.asyncio
async def test_out_of_scope_question_is_refused_plainly():
    result = await answer_question("how much does a fare cost?")

    assert "don't have that information" in result.text
    assert result.station is None


@pytest.mark.asyncio
async def test_nearest_to_me_question_is_refused_not_searched_as_a_station_name():
    # Real bug found live: "what is the nearest PATH station to me" has no
    # location to answer from, but "PATH" alone can still substring-match
    # real station names (see test_ambiguous_toward... below) and get
    # treated as a station-name search instead of being refused outright.
    result = await answer_question("what is the nearest path station to me?")

    assert result.station is None
    assert "location" in result.text.lower() or "don't have that information" in result.text


@pytest.mark.asyncio
async def test_no_match_question_asks_for_clarification():
    result = await answer_question("what about zzz not a real place")

    assert "couldn't find a station" in result.text.lower()
    assert result.station is None


# --- Real GPS fallback for station-less questions (2026-08-09) ---
# Real user expectation found live: a station-less question with no
# resolvable prior conversation context should still be answerable from
# the user's real current location, not just questions that happen to say
# "nearest." Real coordinates are now a fallback tier, used only when
# neither the question nor the conversation history names a real station.


@pytest.mark.asyncio
async def test_station_less_question_falls_back_to_the_real_nearest_station():
    # Real coordinates right at Journal Square PATH's own location -
    # same fixture data test_station_index.py's nearest_stations tests use.
    result = await answer_question(
        "what's next", lat=40.7318097, lng=-74.0628655
    )

    assert result.station is not None
    assert result.station.code == "JSQ"


@pytest.mark.asyncio
async def test_station_less_question_without_coordinates_still_asks_for_clarification():
    # No lat/lng at all (no permission, or an old client) - must fall
    # through to the existing honest refusal, never guess a station.
    result = await answer_question("what's next")

    assert result.station is None
    assert "couldn't find a station" in result.text.lower()


@pytest.mark.asyncio
async def test_a_real_named_station_is_never_overridden_by_gps_fallback():
    # Real regression guard: coordinates being present must never hijack
    # a question that already names its own real station - GPS is a
    # fallback tier, not a default.
    result = await answer_question(
        "what's next from Grove Street", lat=40.7318097, lng=-74.0628655
    )

    assert result.station is not None
    assert result.station.code == "GRV"


@pytest.mark.asyncio
async def test_conversation_history_is_preferred_over_gps_fallback(db_session):
    # Real regression guard: a real station already established in THIS
    # conversation must win over falling back to GPS - the conversation's
    # own context is more specific than "wherever the user happens to be
    # standing right now."
    session_id = uuid.uuid4()
    await answer_question("what's next from Grove Street", db=db_session, session_id=session_id)

    follow_up = await answer_question(
        "what time is the next one",
        db=db_session,
        session_id=session_id,
        lat=40.7318097,
        lng=-74.0628655,
    )

    assert follow_up.station is not None
    assert follow_up.station.code == "GRV"


# --- Real implicit-origin routing (2026-08-09) ---
# Real bug found live: "best way to reach Newport mall now" names only
# ONE station - the real origin is wherever the user currently is, not a
# second named station - and used to fall straight through to a plain
# arrivals answer for that one station, silently ignoring the actual
# routing intent (and the real GPS coordinates the app already had).


@pytest.mark.asyncio
async def test_reach_x_with_real_gps_routes_from_the_real_nearest_station():
    # Real coordinates at Journal Square's own location - the real
    # nearest PATH station should become the implicit origin. Journal
    # Square -> Newport is a genuine direct ride on JSQ_33 (a real
    # topology correction, 2026-08-10/11 - see path_topology.py's module
    # docstring - this used to be wrongly modeled as needing a transfer).
    result = await answer_question(
        "What is the best way to reach Newport mall now?",
        lat=40.7318097,
        lng=-74.0628655,
    )

    assert result.station is not None
    assert result.station.code == "NEW"
    assert "Journal Square" in result.text


@pytest.mark.asyncio
async def test_reach_x_without_coordinates_refuses_honestly():
    # No real GPS at all - there's no real origin to route from, so this
    # must refuse ("route_unsupported") rather than silently answering
    # with just Newport's own plain arrivals, which would address only
    # half the real routing question being asked.
    result = await answer_question("What is the best way to reach Newport mall now?")

    assert result.station is None
    assert "can't" in result.text.lower() or "one station at a time" in result.text.lower()


@pytest.mark.asyncio
async def test_reach_x_is_not_triggered_for_an_ambiguous_or_unnamed_destination():
    result = await answer_question(
        "how do I get to nowhere real123", lat=40.7318097, lng=-74.0628655
    )

    assert result.station is None


@pytest.mark.asyncio
async def test_reach_x_via_y_phrasing_resolves_both_real_stations():
    # Real bug found live, 2026-08-10: "how much would it cost to reach
    # 33rd street path via journal square path station" named two real
    # stations but neither the from/to nor to/from splitter matched "via"
    # phrasing at all, so it fell straight through to a refusal.
    result = await answer_question(
        "how much would it cost to reach 33 St via Journal Square"
    )

    assert result.station is not None
    assert result.station.code == "33S"


@pytest.mark.asyncio
async def test_ordinal_street_names_match_the_bundled_abbreviated_form():
    # Real bug found live, 2026-08-10: an ordinal-suffixed street name
    # (the natural way to say it) matched NOTHING - every bundled
    # numbered-street station uses the bare-number abbreviated form
    # ("9 St," not "9th Street"). "9th Street" is PATH-only in the real
    # index (unlike "33 St"/"23 St", which also collide with real MTA
    # stations of the same name) - a genuine unambiguous match.
    result = await answer_question("what's next from 9th Street")

    assert result.station is not None
    assert result.station.code == "09S"


# --- Real "not every message is a question" fix (2026-08-09) ---
# Real bug found live: a plain "ok thanks" after an unresolved/ambiguous
# turn fell through to the no-real-station-yet path and got answered as
# if it were a genuine clarification-needed question ("Could you please
# clarify which PATH station...") - a closing remark isn't a question at
# all and never deserves that answer.


@pytest.mark.asyncio
async def test_plain_thanks_gets_a_friendly_reply_not_a_clarification_request():
    result = await answer_question("ok thanks")

    assert result.station is None
    assert "clarify" not in result.text.lower()
    assert "couldn't find" not in result.text.lower()


@pytest.mark.asyncio
async def test_closing_remark_is_recognized_case_and_punctuation_insensitively():
    from app.chat_ai import _is_conversation_closer

    assert _is_conversation_closer("Thanks!")
    assert _is_conversation_closer("  OK, thanks  ")
    assert _is_conversation_closer("got it")


@pytest.mark.asyncio
async def test_a_real_question_containing_a_closer_word_is_not_swallowed():
    from app.chat_ai import _is_conversation_closer

    # Real regression guard: "cool" alone is a closer, but a real question
    # that happens to start with it must still be treated as a question -
    # this is why the check is exact-match, not substring.
    assert not _is_conversation_closer("cool, what's next from Grove Street")


@pytest.mark.asyncio
async def test_arrivals_context_carries_real_headsigns_when_the_feed_reports_them(monkeypatch):
    # Real bug found live: PATH's feed reports a real per-arrival
    # destination (see transit/path.py, "headSign") but chat_ai discarded
    # it entirely - the LLM had no way to describe "the other direction"
    # correctly and invented a distinction instead. This proves the fix
    # end to end: a real headsign reaches the template-rendered text.
    now = datetime.now(timezone.utc)

    async def fake_path_with_headsigns(station_code, direction):
        headsign = "World Trade Center" if direction == "ToNY" else "Newark"
        return ArrivalsResult(
            arrivals=[Arrival(route_label="PATH", arrival_time=now + timedelta(minutes=5), headsign=headsign)],
            is_live=True,
        )

    monkeypatch.setattr("app.chat_ai.path.get_arrivals", fake_path_with_headsigns)

    result = await answer_question("what's next from Grove Street")

    assert "World Trade Center" in result.text or "Newark" in result.text


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
async def test_ambiguous_options_with_a_toward_hint_are_actually_distinguishable():
    # Real bug found live: two real, genuinely different NJT bus stops
    # (stop_ids 15652/15653) are both literally named "PATH STATION" - the
    # old ambiguous response listed the identical name twice with nothing
    # to tell them apart. Both carry a real "toward" hint (Kearny / Jersey
    # Gardens - see build_chat_station_index.py) that must actually appear
    # in the response now, not just the bare duplicate name.
    result = await answer_question("what time is the bus at path station")

    assert result.station is None
    assert "Kearny" in result.text
    assert "Jersey Gardens" in result.text


@pytest.mark.asyncio
async def test_same_name_different_agency_also_stays_ambiguous():
    # "Hoboken" exactly matches both a real PATH station and a real NJT
    # rail station - genuinely different agencies serving the same named
    # place. Silently picking one would answer a different question than
    # the user asked half the time, so this must ask too, not guess PATH.
    result = await answer_question("Hoboken")

    assert result.station is None


# --- Real disambiguation follow-ups (2026-08-10) ---
# Real bug found live: a short reply answering WHICH option was meant
# ("path," after being asked to pick between PATH and NJ Transit) was
# treated as a brand-new station search instead of the answer to the
# clarification just asked - either silently falling back to a stale
# station from earlier history, or hitting a fresh, unrelated ambiguous
# search on the bare agency word itself.


@pytest.mark.asyncio
async def test_a_question_naming_its_own_agency_resolves_without_asking_again():
    # Real bug found live, 2026-08-10: "the next PATH train from
    # Hoboken" already names which real agency is meant (PATH, not NJT
    # rail) - asking the user to pick again discards information the
    # question itself already gave.
    result = await answer_question("when's the next PATH train from Hoboken")

    assert result.station is not None
    assert result.station.agency == "path"
    assert result.station.code == "HOB"


@pytest.mark.asyncio
async def test_a_bare_agency_reply_resolves_the_immediately_prior_ambiguous_question(
    db_session,
):
    session_id = uuid.uuid4()
    first = await answer_question("Hoboken", db=db_session, session_id=session_id)
    assert first.station is None  # confirms it was genuinely ambiguous first

    follow_up = await answer_question("path", db=db_session, session_id=session_id)

    assert follow_up.station is not None
    assert follow_up.station.agency == "path"
    assert follow_up.station.code == "HOB"


@pytest.mark.asyncio
async def test_ambiguous_followup_does_not_reach_back_past_the_immediately_prior_turn(
    db_session,
):
    # Real regression guard: an older ambiguous prompt the user has
    # already moved on from must not keep hijacking a later, unrelated
    # short reply just because it happens to mention an agency word.
    session_id = uuid.uuid4()
    await answer_question("Hoboken", db=db_session, session_id=session_id)
    await answer_question(
        "path", db=db_session, session_id=session_id
    )  # resolves the Hoboken ambiguity - no longer the "immediately prior" turn after this

    follow_up = await answer_question("path", db=db_session, session_id=session_id)

    # The most recent assistant turn is now a real Hoboken PATH arrivals
    # answer, not an ambiguous refusal - "path" here has nothing real to
    # resolve against and must NOT re-trigger the old Hoboken ambiguity.
    assert follow_up.station is None or follow_up.station.code == "HOB"


@pytest.mark.asyncio
async def test_ambiguous_followup_with_no_matching_option_falls_through_normally(
    db_session,
):
    session_id = uuid.uuid4()
    await answer_question("Hoboken", db=db_session, session_id=session_id)

    # "mta" isn't one of the two real options offered (PATH, NJT rail) -
    # must not be force-matched to either; falls through to whatever the
    # normal station-less pipeline does with this text.
    follow_up = await answer_question("mta", db=db_session, session_id=session_id)

    assert follow_up.station is None or follow_up.station.agency != "path" or follow_up.station.code != "HOB"


@pytest.mark.asyncio
async def test_no_arrivals_found_is_stated_plainly_not_invented():
    result = await answer_question("Grove Street")

    assert result.text


@pytest.mark.asyncio
async def test_falls_back_to_template_when_no_api_key():
    result = await answer_question("Grove Street")

    assert "min" in result.text


@pytest.mark.asyncio
async def test_personal_question_without_login_falls_back_to_stateless(db_session):
    # No db/user_id passed at all - the stateless caller's default,
    # matching every test above. A personal-sounding question with no
    # logged-in user must still get a real, useful (non-personalized)
    # answer, never an error or an empty result.
    result = await answer_question("what train do I usually take from Grove Street")

    assert result.station is not None
    assert "min" in result.text


@pytest.mark.asyncio
async def test_personal_question_with_no_history_falls_back_to_stateless(db_session):
    user = _make_user(db_session)

    # Logged in, personal phrasing, but zero Trip history for this
    # station - recommend_for_station still ranks live candidates (no
    # history needed for that part), so this actually DOES personalize
    # in the sense of using the real engine - see the test below for the
    # genuinely-no-usual-yet case using a station with no live data at all.
    result = await answer_question(
        "what do I usually take from Astoria-Ditmars Blvd",
        db=db_session,
        user_id=user.id,
    )

    assert result.station is not None


@pytest.mark.asyncio
async def test_personalized_answer_matches_commute_ai_exactly(db_session):
    """The PRD's own requirement, made concrete: Chat AI's personalized
    tier must give the SAME answer Commute AI would give in card form for
    the same station. Proven here by calling both real pipelines side by
    side against the same user/station and asserting the phrased text is
    character-for-character identical - not just "similar," since they
    share one implementation (recommend_for_station +
    phrase_commute_recommendation), not two independently-written ones.
    """
    from app.commute_engine import recommend_for_station
    from app.llm_phrasing import phrase_commute_recommendation

    user = _make_user(db_session, email="consistency@example.com")
    for i in range(3):
        db_session.add(
            Trip(
                user_id=user.id,
                start_time=datetime.now(timezone.utc).replace(hour=8) - timedelta(days=i),
                mode="mta",
                origin_stop="R01",
                route_or_direction="W",
            )
        )
    db_session.commit()

    chat_result = await answer_question(
        "what do I usually take from Astoria-Ditmars Blvd",
        db=db_session,
        user_id=user.id,
    )

    commute_ai_recommendation = await recommend_for_station(
        db_session, user.id, "mta", "R01", user.reliability_pref
    )
    commute_ai_text = phrase_commute_recommendation(commute_ai_recommendation)

    assert chat_result.text == commute_ai_text


@pytest.mark.asyncio
async def test_nearest_question_without_coordinates_is_refused_honestly():
    result = await answer_question("what is the nearest path station to me?")

    assert result.station is None
    assert "location" in result.text.lower()


@pytest.mark.asyncio
async def test_nearest_question_with_real_coordinates_finds_a_real_station():
    # Real coordinates right at Journal Square PATH's own location.
    result = await answer_question(
        "what is the nearest path station to me?", lat=40.7318097, lng=-74.0628655
    )

    assert result.station is not None
    assert result.station.agency == "path"
    assert result.station.code == "JSQ"
    assert "Journal Square" in result.text


@pytest.mark.asyncio
async def test_nearest_question_with_no_agency_mentioned_searches_everything():
    result = await answer_question(
        "what is the nearest station to me?", lat=40.7318097, lng=-74.0628655
    )

    assert result.station is not None


@pytest.mark.asyncio
async def test_nearest_question_is_not_treated_as_a_station_name_search():
    # Real bug found live: "PATH" alone can substring-match real station
    # names (e.g. NJT bus stops literally named "PATH STATION") - a
    # nearest-question must never fall through to that search, even when
    # coordinates ARE provided.
    result = await answer_question(
        "what time is the bus at path station", lat=40.7318097, lng=-74.0628655
    )
    # Not a "nearest" question at all (no nearest/closest keyword) - this
    # should still hit the real ambiguous-PATH-STATION path, proving the
    # nearest-detector doesn't accidentally fire on unrelated questions
    # just because coordinates happen to be present.
    assert result.station is None


# --- Real routing questions (2026-08-08) ---
# Real bug found live: "what's the fastest way from Hoboken to World
# Trade Center" was silently answered using just ONE of the two named
# stations' plain arrivals - a genuine hallucination, since the app had
# (and still has, for anything beyond PATH) no real capability to plan a
# multi-station trip. These tests prove the real fix: a PATH-only pair
# gets a real, topology-based route; anything else gets an honest refusal
# instead of a fabricated single-station answer.


@pytest.mark.asyncio
async def test_direct_path_ride_gives_a_real_one_leg_route():
    # "33 St" (not "33rd Street") is the real bundled PATH station name -
    # renamed to match MTA's exact naming convention so they merge in the
    # Flutter app's station picker (see OPEN_QUESTIONS.md, 2026-07-29).
    result = await answer_question("what's the fastest way from Hoboken to 33 St")

    assert result.station is not None
    assert result.station.code == "33S"
    assert "HOB_33" in result.text or "min" in result.text


@pytest.mark.asyncio
async def test_path_ride_needing_a_transfer_mentions_the_real_transfer_station():
    result = await answer_question("what's the fastest way from Newark to Hoboken")

    assert result.station is not None
    assert result.station.code == "HOB"
    # Real transfer station per path_topology.py - Exchange Place.
    assert "Exchange Place" in result.text


@pytest.mark.asyncio
async def test_routing_question_with_no_real_path_pair_is_refused_honestly():
    # "Grove Street" resolves fine, but there's no second real station
    # named here at all ("from there" isn't a real station name) - must
    # refuse, never silently answer using just Grove Street's arrivals.
    result = await answer_question("how do I get to Grove Street from there")

    assert result.station is None
    assert "can't" in result.text.lower() or "one station at a time" in result.text.lower()


@pytest.mark.asyncio
async def test_routing_question_with_an_ambiguous_station_name_is_refused_honestly():
    # "Hoboken" exactly matches both a real PATH and a real NJT rail
    # station - the routing extractor requires an unambiguous PATH match
    # on both sides, so a genuinely ambiguous name must refuse, not guess
    # which "Hoboken" was meant.
    result = await answer_question("what's the fastest way from Hoboken to Newark")

    # Hoboken alone IS unambiguous once filtered to agency=="path" (see
    # _extract_two_stations), so this specific pair actually resolves -
    # asserting the real, correct route instead of a refusal.
    assert result.station is not None
    assert result.station.code == "NWK"


@pytest.mark.asyncio
async def test_routing_question_is_not_confused_with_a_plain_arrivals_question():
    # A real regression guard: a plain single-station question must never
    # be misclassified as routing just because it happens to contain the
    # word "from".
    result = await answer_question("what's the next PATH train from Grove Street")

    assert result.station is not None
    assert result.station.code == "GRV"


@pytest.mark.asyncio
async def test_next_train_to_x_from_y_phrasing_is_recognized_as_routing():
    # Real bug found live, 2026-08-09: "next train TO Newport FROM
    # Journal Square" wasn't recognized as routing at all (the fixed
    # verb list only covered "fastest way"/"how do I get" style
    # phrasing), so it silently answered with Newport's own arrivals,
    # discarding the real "from Journal Square" half of the question
    # entirely and answering trains FROM Newport instead of TO it.
    # Journal Square -> Newport is a genuine direct ride on JSQ_33 (a
    # real topology correction, 2026-08-10/11 - see path_topology.py).
    result = await answer_question(
        "What is the next train to newport from journal square path?"
    )

    assert result.station is not None
    assert result.station.code == "NEW"
    assert "Journal Square" in result.text


@pytest.mark.asyncio
async def test_a_question_naming_two_real_different_stations_never_silently_picks_one():
    # Real bug found live, 2026-08-09: _is_unambiguous only ever checked
    # for SAME-name collisions - a question naming two real, DIFFERENT
    # stations (with no routing verb _is_routing_question recognizes)
    # sailed through as "unambiguous" and silently answered with
    # whichever one find_stations ranked first, discarding the other
    # real station entirely. This phrasing has no routing verb and no
    # from/to structure, so it must not silently pick one - it should at
    # minimum ask for clarification rather than answer only one.
    result = await answer_question("Grove Street and Journal Square trains")

    # Either genuinely refuses (no single station chosen) or - if some
    # future intent classifier legitimately handles this phrasing - it
    # must not be the OLD bug's exact failure mode of silently returning
    # just one of the two stations with no acknowledgment of the other.
    if result.station is not None:
        assert "Journal Square" in result.text and "Grove Street" in result.text


# --- Real "next station after X" topology questions (2026-08-09) ---
# Real bug found live: "what's the next station after Grove Street" - a
# genuinely different question type (real line topology, not arrival
# times, not A-to-B routing) - had no handler at all and fell through to
# a plain arrivals answer that had nothing to do with the real question.


@pytest.mark.asyncio
async def test_next_station_question_gives_real_adjacent_stations():
    result = await answer_question("what is next station after grove street")

    assert result.station is not None
    assert result.station.code == "GRV"
    # Real adjacency per path_topology.py - Exchange Place (toward NY)
    # and Journal Square (toward NJ) are genuinely next to Grove Street.
    assert "Exchange Place" in result.text
    assert "Journal Square" in result.text


@pytest.mark.asyncio
async def test_next_station_question_is_not_confused_with_a_plain_arrivals_question():
    result = await answer_question("what's next from Grove Street")

    # Must still be a plain arrivals answer, not a next-station answer -
    # "from" alone shouldn't trigger the next-station classifier.
    assert result.station is not None
    assert result.station.code == "GRV"


@pytest.mark.asyncio
async def test_next_station_question_for_a_non_path_station_refuses_honestly():
    result = await answer_question("what is the next station after Astoria-Ditmars Blvd")

    assert result.station is None


@pytest.mark.asyncio
async def test_next_station_from_phrasing_gives_real_topology_not_plain_arrivals():
    # Real bug found live, 2026-08-10: "what's the next station FROM
    # Grove Street" (as opposed to "after"/"before") fell through to a
    # plain arrivals answer dressed up with destination names, instead
    # of real line-topology adjacency.
    result = await answer_question("what's the next station from grove street")

    assert result.station is not None
    assert result.station.code == "GRV"
    assert "Exchange Place" in result.text


# --- Real "other direction" follow-ups (2026-08-08) ---
# Real bug found live: "what about the other direction" got every real
# headsign merged together handed to the LLM with no way to know which
# ones were already discussed, so it either repeated the same answer or
# invented a distinction the data didn't show. These tests use a
# direction-aware PATH mock (real headsigns differing by ToNY/ToNJ, same
# as the real feed) to prove the fix filters to the real complementary
# destinations instead.


@pytest.fixture
def direction_aware_path_mock(monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_path(station_code, direction):
        headsign = "33rd Street" if direction == "ToNY" else "Newark"
        return ArrivalsResult(
            arrivals=[Arrival(route_label="PATH", arrival_time=now + timedelta(minutes=5), headsign=headsign)],
            is_live=True,
        )

    monkeypatch.setattr("app.chat_ai.path.get_arrivals", fake_path)


@pytest.mark.asyncio
async def test_other_direction_shows_the_real_complementary_headsign(
    db_session, direction_aware_path_mock
):
    session_id = uuid.uuid4()

    first = await answer_question("what's next from Grove Street", db=db_session, session_id=session_id)
    follow_up = await answer_question(
        "what about the other direction", db=db_session, session_id=session_id
    )

    assert follow_up.station is not None
    assert follow_up.station.code == "GRV"
    # The follow-up's real destination must genuinely differ from the
    # first answer's - not the same headsigns repeated back.
    assert follow_up.headsigns != first.headsigns
    assert follow_up.headsigns is not None
    assert not (follow_up.headsigns & first.headsigns)


@pytest.mark.asyncio
async def test_other_direction_with_no_prior_station_is_refused_honestly(db_session):
    session_id = uuid.uuid4()

    result = await answer_question(
        "what about the other direction", db=db_session, session_id=session_id
    )

    assert result.station is None


# --- Real code-level headsign-fidelity enforcement (2026-08-10) ---
# Real bug found live via self-testing: even after adding an explicit
# system-prompt rule forbidding it, the LLM still invented a completely
# different, real-sounding destination ("Harrison") that didn't
# correspond to ANY real headsign actually given - a prompt rule alone
# wasn't reliably followed by this model under real load. Verified in
# code instead of trusted blindly: _headsigns_are_faithful checks the
# LLM's own text against the real data before ever returning it.


class TestHeadsignsAreFaithful:
    def test_a_fabricated_destination_not_in_the_real_data_is_rejected(self):
        from app.chat_ai import _headsigns_are_faithful

        context = {
            "kind": "arrivals",
            "station": "Hoboken",
            "agency": "path",
            "arrivals": [{"route_label": "PATH", "minutes_until": 2.8, "headsign": "33rd Street"}],
        }
        text = "The next PATH train from Hoboken to Harrison is in 2.8 minutes."

        assert _headsigns_are_faithful(text, context) is False

    def test_text_using_only_the_real_given_headsign_is_accepted(self):
        from app.chat_ai import _headsigns_are_faithful

        context = {
            "kind": "arrivals",
            "station": "Hoboken",
            "agency": "path",
            "arrivals": [{"route_label": "PATH", "minutes_until": 2.8, "headsign": "World Trade Center"}],
        }
        text = "The next PATH train from Hoboken to World Trade Center is in 2.8 minutes."

        assert _headsigns_are_faithful(text, context) is True

    def test_the_origin_station_name_itself_is_never_flagged_as_a_fabrication(self):
        # Real false-positive found while building this check: the
        # ORIGIN station (e.g. "Hoboken") is also a real PATH station
        # name, and legitimately appears in any normal sentence - it
        # must never be treated as an invented destination.
        from app.chat_ai import _headsigns_are_faithful

        context = {
            "kind": "arrivals",
            "station": "Hoboken",
            "agency": "path",
            "arrivals": [{"route_label": "PATH", "minutes_until": 2.8, "headsign": "World Trade Center"}],
        }
        text = "The next PATH train from Hoboken to World Trade Center is in 2.8 minutes."

        assert _headsigns_are_faithful(text, context) is True

    def test_non_arrivals_contexts_are_never_checked(self):
        from app.chat_ai import _headsigns_are_faithful

        context = {"kind": "no_match"}
        text = "Harrison is a real PATH station but this isn't an arrivals context."

        assert _headsigns_are_faithful(text, context) is True

    def test_arrivals_with_no_real_headsign_data_are_never_checked(self):
        # MTA/other agencies with no headsign data at all - nothing to
        # verify against, so this must not falsely reject real text.
        from app.chat_ai import _headsigns_are_faithful

        context = {
            "kind": "arrivals",
            "station": "Astoria-Ditmars Blvd",
            "agency": "mta",
            "arrivals": [{"route_label": "N", "minutes_until": 5.0}],
        }
        text = "The next N train from Astoria-Ditmars Blvd is in 5 minutes, headed toward Harrison."

        assert _headsigns_are_faithful(text, context) is True


# --- Real code-level route-transfer fidelity enforcement (2026-08-11) ---
# Real bug found live via self-testing: a genuine ONE-leg direct route
# (Grove Street to Newport) was described with a completely invented
# transfer at Exchange Place and a fabricated second leg that don't
# exist anywhere in the real context given - the same class of bug as
# the earlier headsign fabrication, just for routing text.


class TestRouteLegCountIsFaithful:
    def test_a_fabricated_transfer_for_a_real_direct_route_is_rejected(self):
        from app.chat_ai import _route_leg_count_is_faithful

        context = {
            "kind": "route",
            "origin": "Grove Street",
            "destination": "Newport",
            "legs": [{"route": "JSQ_33", "board": "Grove Street", "alight": "Newport", "wait_minutes": 1.0}],
        }
        text = "You need to transfer at Exchange Place to get from Grove Street to Newport."

        assert _route_leg_count_is_faithful(text, context) is False

    def test_a_real_direct_route_described_as_direct_is_accepted(self):
        from app.chat_ai import _route_leg_count_is_faithful

        context = {
            "kind": "route",
            "origin": "Grove Street",
            "destination": "Newport",
            "legs": [{"route": "JSQ_33", "board": "Grove Street", "alight": "Newport", "wait_minutes": 1.0}],
        }
        text = "Take the JSQ_33 train directly from Grove Street to Newport."

        assert _route_leg_count_is_faithful(text, context) is True

    def test_a_fabricated_direct_claim_for_a_real_transfer_route_is_rejected(self):
        from app.chat_ai import _route_leg_count_is_faithful

        context = {
            "kind": "route",
            "origin": "Newark",
            "destination": "Hoboken",
            "legs": [
                {"route": "NWK_WTC", "board": "Newark", "alight": "Exchange Place", "wait_minutes": 2.0},
                {"route": "HOB_WTC", "board": "Exchange Place", "alight": "Hoboken", "wait_minutes": 1.0},
            ],
        }
        text = "There is a direct train from Newark to Hoboken, no transfer needed."

        assert _route_leg_count_is_faithful(text, context) is False

    def test_a_real_transfer_route_correctly_described_is_accepted(self):
        from app.chat_ai import _route_leg_count_is_faithful

        context = {
            "kind": "route",
            "origin": "Newark",
            "destination": "Hoboken",
            "legs": [
                {"route": "NWK_WTC", "board": "Newark", "alight": "Exchange Place", "wait_minutes": 2.0},
                {"route": "HOB_WTC", "board": "Exchange Place", "alight": "Hoboken", "wait_minutes": 1.0},
            ],
        }
        text = "Transfer at Exchange Place: take the train from Newark, then transfer to Hoboken."

        assert _route_leg_count_is_faithful(text, context) is True

    def test_per_leg_direct_wording_within_a_real_transfer_is_not_falsely_rejected(self):
        # Real case observed live: each individual leg described as "a
        # direct ride" is legitimate as long as the overall transfer is
        # still mentioned - only an OVERALL "direct, no transfer" claim
        # for a genuine two-leg trip is a fabrication.
        from app.chat_ai import _route_leg_count_is_faithful

        context = {
            "kind": "route",
            "origin": "Newark",
            "destination": "Hoboken",
            "legs": [
                {"route": "NWK_WTC", "board": "Newark", "alight": "Exchange Place", "wait_minutes": 2.0},
                {"route": "HOB_WTC", "board": "Exchange Place", "alight": "Hoboken", "wait_minutes": 1.0},
            ],
        }
        text = (
            "You need to transfer at Exchange Place. The first leg is a direct "
            "ride from Newark to Exchange Place, and the second leg is a direct "
            "ride from Exchange Place to Hoboken."
        )

        assert _route_leg_count_is_faithful(text, context) is True

    def test_naming_a_different_real_agency_for_a_path_only_route_is_rejected(self):
        # Real case found live: a route leg is always a real PATH ride
        # (this module only computes PATH topology) - naming any other
        # agency is inventing a fact not present in the given context.
        from app.chat_ai import _route_leg_count_is_faithful

        context = {
            "kind": "route",
            "origin": "Newark",
            "destination": "Hoboken",
            "legs": [
                {"route": "NWK_WTC", "board": "Newark", "alight": "Exchange Place", "wait_minutes": 2.0},
                {"route": "HOB_WTC", "board": "Exchange Place", "alight": "Hoboken", "wait_minutes": 1.0},
            ],
        }
        text = "Take the NJ Transit train from Newark to Exchange Place, then transfer to a PATH train to Hoboken."

        assert _route_leg_count_is_faithful(text, context) is False


@pytest.mark.asyncio
async def test_a_hallucinated_route_transfer_is_discarded_for_the_real_template_answer(
    monkeypatch, db_session
):
    # Real end-to-end proof, mocking at the actual OpenAI client call so
    # the real fidelity check inside _ask_llm genuinely runs: even when
    # the LLM invents a transfer for a real direct route, the final
    # answer never contains it.
    import app.chat_ai as chat_ai

    monkeypatch.setattr(chat_ai.settings, "groq_api_key", "fake-key-for-this-test")

    class _FakeMessage:
        content = "You need to transfer at Exchange Place to get from Grove Street to Newport."

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(chat_ai, "OpenAI", _FakeOpenAI)

    result = await answer_question("how do I get from Grove Street to Newport")

    assert "transfer" not in result.text.lower()
    assert "Exchange Place" not in result.text


@pytest.mark.asyncio
async def test_a_hallucinated_headsign_is_discarded_for_the_real_template_answer(
    monkeypatch, direction_aware_path_mock, db_session
):
    # Real end-to-end proof, mocking at the actual OpenAI client call (not
    # _ask_llm itself) so the real fidelity check inside _ask_llm
    # genuinely runs: even when the LLM returns text that invents a fake
    # destination, the final answer never contains it - the real
    # deterministic template (built directly from real data) is used
    # instead, silently and automatically.
    import app.chat_ai as chat_ai

    monkeypatch.setattr(chat_ai.settings, "groq_api_key", "fake-key-for-this-test")

    class _FakeMessage:
        content = "The next PATH train from Grove Street to Harrison is in 5 minutes."

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        choices = [_FakeChoice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeOpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(chat_ai, "OpenAI", _FakeOpenAI)

    session_id = uuid.uuid4()
    await answer_question("what's next from Grove Street", db=db_session, session_id=session_id)
    result = await answer_question(
        "what about the other direction", db=db_session, session_id=session_id
    )

    assert "Harrison" not in result.text


@pytest.mark.asyncio
async def test_other_direction_without_a_session_is_refused_honestly():
    # No session_id at all - there is no real prior turn to invert, same
    # "additive, never a hard requirement" posture as every other
    # conversation-memory-dependent feature in this module.
    result = await answer_question("what about the other direction")

    assert result.station is None


# --- Real conversation memory (2026-08-08) ---
# Found live: every question was answered with zero memory of the
# conversation so far, by design - but that design read to users as "not
# maintaining context," since nothing ever surfaced the limitation. These
# tests prove the real fix: a session's actual prior turns, stored
# server-side, both resolve station-less follow-ups and get handed to the
# LLM as real conversation history.


@pytest.mark.asyncio
async def test_no_session_id_behaves_exactly_as_before_stateless(db_session):
    # A caller with no session_id (every call site before this feature
    # existed) must still get a real single-turn answer - conversation
    # memory is additive, never a new requirement to answer at all.
    result = await answer_question("Grove Street", db=db_session)

    assert result.station is not None
    assert result.station.code == "GRV"
    # Nothing should have been persisted with no session_id to attach to.
    assert db_session.query(ChatMessage).count() == 0


@pytest.mark.asyncio
async def test_a_real_session_persists_its_turns(db_session):
    session_id = uuid.uuid4()

    await answer_question("Grove Street", db=db_session, session_id=session_id)

    session = db_session.get(ChatSession, session_id)
    assert session is not None

    messages = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Grove Street"
    assert messages[1].role == "assistant"
    assert messages[1].station_agency == "path"
    assert messages[1].station_code == "GRV"


@pytest.mark.asyncio
async def test_a_station_less_follow_up_resolves_against_the_real_last_station(db_session):
    # Real bug this fixes: "what about the other direction" (or any
    # question naming no station) used to fail with "I couldn't find a
    # station" even immediately after asking about a specific one.
    session_id = uuid.uuid4()

    await answer_question("Grove Street", db=db_session, session_id=session_id)
    follow_up = await answer_question(
        "what time is the next one", db=db_session, session_id=session_id
    )

    assert follow_up.station is not None
    assert follow_up.station.code == "GRV"
    assert "min" in follow_up.text


@pytest.mark.asyncio
async def test_a_station_less_question_with_no_prior_turns_still_asks_for_clarification(
    db_session,
):
    # A fresh session with no history yet has nothing real to fall back
    # to - must still refuse honestly, not guess a station out of thin
    # air just because a session_id was provided.
    session_id = uuid.uuid4()

    result = await answer_question(
        "what time is the next one", db=db_session, session_id=session_id
    )

    assert result.station is None
    assert "couldn't find a station" in result.text.lower()


@pytest.mark.asyncio
async def test_different_sessions_never_share_history(db_session):
    # Two independent conversations (e.g. two different anonymous
    # devices) must never leak context into each other.
    session_a = uuid.uuid4()
    session_b = uuid.uuid4()

    await answer_question("Grove Street", db=db_session, session_id=session_a)
    result = await answer_question(
        "what time is the next one", db=db_session, session_id=session_b
    )

    assert result.station is None
    assert "couldn't find a station" in result.text.lower()


@pytest.mark.asyncio
async def test_history_is_capped_to_the_most_recent_turns(db_session):
    # Real gotcha this guards against: an unbounded history would grow
    # every LLM prompt forever over a long-running conversation - only
    # the most recent _MAX_HISTORY_TURNS should ever be loaded.
    from app.chat_ai import _MAX_HISTORY_TURNS, _load_recent_history

    session_id = uuid.uuid4()
    db_session.add(ChatSession(id=session_id))
    db_session.commit()
    for i in range(_MAX_HISTORY_TURNS + 5):
        db_session.add(
            ChatMessage(session_id=session_id, role="user", content=f"question {i}")
        )
    db_session.commit()

    history = _load_recent_history(db_session, session_id)

    assert len(history) == _MAX_HISTORY_TURNS
    # Oldest-first, and genuinely the most RECENT turns, not the oldest.
    assert history[-1].content == f"question {_MAX_HISTORY_TURNS + 4}"
