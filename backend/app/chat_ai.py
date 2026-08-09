"""Chat AI - both tiers (see PRD Phase 3). User-initiated only, never
proactive. One endpoint, one pipeline for both:

- Stateless tier: answers using only live feed data for a station the
  question itself names - zero dependency on Behavior AI, works with no
  login at all.
- Personalized tier: for a question that reads as personal ("what do I
  usually take from here") from a LOGGED-IN user whose question resolves
  to one real station, answers via commute_engine.recommend_for_station
  - the EXACT SAME function Commute AI's own endpoint calls - and phrases
  it with the exact same phrase_commute_recommendation Commute AI uses.
  This is what makes "Chat AI's personalized tier must give the same
  answer Commute AI would give in card form" (the PRD's own wording)
  structurally true rather than a promise to keep two implementations in
  sync: there is only one implementation. Falls back to the stateless
  arrivals answer (not a refusal) when personal phrasing is detected but
  the user isn't logged in, or when recommend_for_station itself has
  nothing to say (no history, no live data) - a logged-out or cold-start
  user still gets a useful answer, just not a personalized one.

Pipeline, deliberately linear and inspectable (no agentic tool-calling
loop - the LLM never decides what to fetch, it only phrases what this
module already fetched deterministically):
1. station_index.find_stations() resolves the question's station name.
   Zero matches -> fall back to the real last-mentioned station in this
   conversation (see _last_mentioned_station), if one exists; still zero
   -> ask the user to clarify (real refusal, not a guess). Multiple
   matches -> list the real options, let the user pick.
2. A personal question, a logged-in user, and an unambiguous match ->
   try the personalized path first (see above). Anything else, or that
   path coming back empty -> the stateless path: fetch REAL live arrivals
   across every route/direction that agency's station serves (never a
   single arbitrarily-picked route/direction - a chat question doesn't
   specify one the way an app screen selection would).
3. Phrase the real fetched data into an answer, giving the LLM the
   session's real recent turns as conversation history so it can resolve
   a reference like "what about the other direction" - never inventing
   a fact not present in either the live data or that real history. The
   LLM's job is exactly as narrow as llm_phrasing.py's: turn real
   structured data into a sentence, never invent a number, never answer
   a question with no real data behind it (fares, crowding, anything
   outside NYC-metro transit) - it must refuse those plainly instead of
   guessing.

Real conversation memory (added 2026-08-08, see OPEN_QUESTIONS.md): found
live that every question was answered with zero memory of the
conversation so far - by design, but that design read to users as "not
maintaining context," a fair complaint since nothing surfaced the
limitation. chat_session.py's ChatSession/ChatMessage store the literal
transcript server-side, keyed by a CLIENT-generated session id (works for
anonymous callers too, same as everything else in this app). This module
never re-derives history from message text with an LLM call - it's a
plain read of what was actually said, same "real data only" posture as
every other piece of this feature.
"""

import re
import uuid
from dataclasses import dataclass

from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .commute_engine import recommend_for_station
from .core.config import settings
from .llm_phrasing import phrase_commute_recommendation
from .models import ChatMessage, ChatSession, User
from .path_topology import route_between_stations
from .station_index import (
    StationMatch,
    contains_whole,
    find_stations,
    nearest_stations,
    normalize,
    station_for,
)
from .transit import lirr, mta, njt_bus, njt_rail, path
from .transit.models import Arrival, ArrivalsResult

_MAX_ARRIVALS_IN_ANSWER = 5
# How many of the session's most recent turns are given to the LLM as
# real conversation history - bounded so a very long-running chat doesn't
# grow the prompt unboundedly; recent turns are what a follow-up question
# actually needs, not the full history from hours ago.
_MAX_HISTORY_TURNS = 8

_SYSTEM_PROMPT = """You are CommuteOS's transit chat assistant, scoped \
strictly to NYC-metro subway/rail/bus arrival times (MTA, PATH, NJ \
Transit rail and bus, LIRR).

Real recent turns of this same conversation may be included as prior \
chat messages before the current question - use them only to understand \
what a follow-up question is referring to (e.g. "what about the other \
direction" means the direction opposite whatever station/direction was \
just discussed). Never invent a fact that isn't in either the real \
context given below or that real prior conversation. If a prior turn was \
a refusal/clarification (no station was actually resolved), do NOT \
summarize, repeat, or refer back to what was "previously asked" - just \
answer the CURRENT question fresh using only the context given below; \
narrating the conversation's own history back to the user is never the \
correct answer.

You will be given a JSON object with the user's question and a "context" \
field. The context is one of:
- {"kind": "arrivals", "station": ..., "agency": ..., "arrivals": [...]} \
- real live arrival data already fetched for the station the question \
named. Each arrival may include a real "headsign" (its actual \
destination, e.g. "World Trade Center") when the source feed reports \
one - use it to describe WHICH direction/train each arrival is, but \
NEVER invent a headsign/direction for an arrival that has none. Answer \
using ONLY these numbers and headsigns - if asked about "the other \
direction" and this arrivals list mixes multiple real headsigns \
together, describe them as they actually are grouped here; do not \
assume there are exactly two directions or invent a distinction the data \
doesn't show.
- {"kind": "no_match"} - no known station matched the question. Ask the \
user to clarify which station they mean. Do NOT suggest, name, or list \
ANY specific example station names (e.g. do not say "such as X or Y") - \
you have no real list to draw examples from here, and naming any \
station you were not given is inventing one. A plain, generic request \
to clarify is the entire correct answer.
- {"kind": "ambiguous", "options": [...]} - more than one station could \
match, each with "name", "agency", and an optional "toward" (a real \
direction hint, e.g. "Kearny" - two options can share the exact same \
name but have different "toward" values, meaning they are genuinely \
different real stops). List the options using the "toward" value to \
tell them apart whenever it is present, and ask the user to pick one; \
do not silently pick for them.
- {"kind": "out_of_scope"} - the question is not about NYC-metro transit \
arrival times (e.g. fares, crowding levels, weather, anything outside \
subway/rail/bus arrivals). Say plainly you don't have that information - \
never guess or invent an answer.
- {"kind": "no_location"} - the user asked about the nearest/closest \
station but no real location was available. Say plainly you don't have \
their current location; never guess a station.
- {"kind": "nearest", "station": ..., "agency": ..., "distance_miles": \
...} - a real nearest-station answer, already computed from the user's \
real coordinates. State the station name and the real distance in miles \
- never invent a different distance or station.
- {"kind": "route", "origin": ..., "destination": ..., "legs": [{"route": \
..., "board": ..., "alight": ..., "wait_minutes": ...}, ...]} - a real, \
already-computed trip plan between two named stations, one or two real \
legs (a second leg means a real transfer at the first leg's "alight" \
station). State each leg's real wait time; if there are two legs, say \
plainly that a transfer is needed and where.
- {"kind": "route_unsupported"} - the user asked for a route/trip between \
two stations that this app cannot compute (e.g. it needs an agency or \
station pair this app doesn't have real routing logic for). Say plainly \
you can't plan that specific trip yet - never invent a route, a transfer \
station, or a travel time you were not given.

Rules you must never break:
- Never invent a time, a station, a headsign/direction, or a fact not \
present in the given context.
- If context.kind is "arrivals" but the arrivals list is empty, say so \
plainly (no service found right now) rather than inventing a time.
- If asked to plan a trip, find a route, or estimate travel time BETWEEN \
TWO NAMED STATIONS and the context you were given is NOT "route" or \
"route_unsupported" (e.g. it's a plain "arrivals" context for just one \
station), say plainly that you can only give arrival times for one \
station at a time and cannot plan multi-station trips outside the cases \
already computed for you - do not silently answer using just one \
station's arrivals as if it addressed the whole trip.
- If context.kind is "arrivals", the ONLY agency actually serving this \
station is the one named in context["agency"]. If asked what OTHER \
lines/agencies/trains also stop there, say plainly you only know about \
that one agency for this station and do not have real data on any \
other real-world agency that might physically be nearby - never name a \
specific other agency (MTA, NJ Transit, LIRR, etc.) unless it is the \
one actually given in context["agency"].
- Keep the answer to 1-3 short sentences, natural and direct.
- Output only the answer text, no preamble, no quotes around it."""


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    station: StationMatch | None
    # The real, distinct headsigns this answer's arrivals actually
    # showed, when it was a plain single-station arrivals answer with
    # real headsign data (PATH) - what a later "what about the other
    # direction" follow-up needs (see _last_shown_headsigns). None for
    # every other kind of answer (refusals, routing, MTA/other agencies
    # with no headsign data) - never guessed or backfilled.
    headsigns: frozenset[str] | None = None


def _template_answer(context: dict) -> str:
    """Deterministic fallback used when no LLM key is configured or the
    call fails - same fail-soft posture as llm_phrasing.py, never leaves
    the user with no response at all.
    """
    kind = context["kind"]
    if kind == "out_of_scope":
        return "I can only help with real-time subway, rail, and bus arrival times in the NYC area - I don't have that information."
    if kind == "no_location":
        return "I don't have your current location, so I can't tell you the nearest station."
    if kind == "nearest":
        return (
            f"The nearest station is {context['station']}, about "
            f"{context['distance_miles']} miles away."
        )
    if kind == "no_match":
        return "I couldn't find a station matching that - could you tell me the station name?"
    if kind == "ambiguous":
        # Append the real "toward X" hint when one exists, so two options
        # that would otherwise render identically (e.g. two separate real
        # NJT bus stops both literally named "PATH STATION") actually give
        # the user something to distinguish them by - see StationMatch.
        # toward's docstring. Falls back to plain name+agency (unchanged
        # behavior) for options with no toward hint.
        labels = [
            f"{o['name']} (toward {o['toward']})" if o.get("toward") else o["name"]
            for o in context["options"]
        ]
        names = ", ".join(labels)
        return f"A few stations match that - did you mean: {names}?"
    if kind == "route_unsupported":
        return "I can't plan a route between those stations yet - I can only give live arrival times for one station at a time."
    if kind == "route":
        origin = context["origin"]
        destination = context["destination"]
        legs = context["legs"]
        if len(legs) == 1:
            leg = legs[0]
            wait = _format_wait(leg["wait_minutes"])
            return f"Take the {leg['route']} train from {origin} to {destination} - {wait}."
        first, second = legs
        first_wait = _format_wait(first["wait_minutes"])
        second_wait = _format_wait(second["wait_minutes"])
        return (
            f"From {origin}, take the {first['route']} train to {first['alight']} "
            f"({first_wait}), then transfer to the {second['route']} train to "
            f"{destination} ({second_wait})."
        )

    arrivals = context["arrivals"]
    station = context["station"]
    if not arrivals:
        return f"No upcoming arrivals found for {station} right now."
    soonest = arrivals[0]
    headsign = f" toward {soonest['headsign']}" if soonest.get("headsign") else ""
    return f"The next arrival at {station}{headsign} is {soonest['route_label']} in about {soonest['minutes_until']} min."


def _format_wait(wait_minutes: float | None) -> str:
    """Never prints "None min" - a leg with no live arrivals right now
    (real, if rare - PATH's feed occasionally has a gap) says so plainly
    instead of a fabricated/blank number.
    """
    if wait_minutes is None:
        return "no live arrival time available for this leg right now"
    return f"the next one is in about {wait_minutes} min"


def _ask_llm(
    question: str, context: dict, history: list[ChatMessage] | None = None
) -> str | None:
    """[history] is the session's real prior turns, oldest first (see
    _load_recent_history) - included as real prior chat messages so the
    LLM can resolve a reference like "what about the other direction"
    against what was actually said, not asked to guess. None/empty (the
    default, and every call site before conversation memory existed)
    means no history - behaves exactly as before.
    """
    if not settings.groq_api_key:
        return None

    client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
    payload = {"question": question, "context": context}

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for turn in history or []:
        role = "assistant" if turn.role == "assistant" else "user"
        messages.append({"role": role, "content": turn.content})
    messages.append({"role": "user", "content": str(payload)})

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            max_tokens=200,
            messages=messages,
        )
        text = response.choices[0].message.content
        return text.strip() if text else None
    except OpenAIError:
        return None


_CLOSING_REMARKS = {
    "ok", "okay", "ok thanks", "okay thanks", "thanks", "thank you",
    "thanks!", "thank you!", "cool", "cool thanks", "great thanks",
    "got it", "alright", "alright thanks", "k", "kk", "nice", "perfect",
}


def _is_conversation_closer(question: str) -> bool:
    """Detects a plain acknowledgment/closing remark ("ok thanks", "got
    it") - a real bug found live: these were falling through to
    _last_mentioned_station's no-real-station-yet case and getting
    answered as if they were a genuine clarification-needed question
    ("Could you please clarify which PATH station...") - a real, if
    minor, hallucination-adjacent bug, since "ok thanks" isn't a
    question at all and doesn't deserve an answer that pretends it was
    asking about a station. Deliberately an exact-match set, not a
    substring check - these phrases are short/common enough that
    substring-matching them inside a real question (e.g. "cool, what
    about Grove Street") would wrongly swallow it.
    """
    normalized = re.sub(r"[^a-z ]", "", question.lower()).strip()
    return normalized in _CLOSING_REMARKS


def _is_out_of_scope(question: str) -> bool:
    """Cheap, explainable keyword gate for the clearest out-of-scope
    cases (fares, crowding, weather) - deliberately not the LLM's call,
    since asking the LLM to self-police scope is exactly the kind of
    judgment call that can drift; a fixed list is auditable. This is a
    narrow, additive check - it only ever adds an out-of-scope refusal,
    never overrides a real station match found below.

    Location-dependent ("nearest"/"closest") questions are handled
    separately by _is_nearest_question - NOT here - since as of
    2026-08-08 those are genuinely answerable when the client sends real
    coordinates (see answer_question), unlike fares/crowding/weather,
    which this app can never answer regardless of what it's given.
    """
    lowered = question.lower()
    out_of_scope_terms = ("fare", "cost", "price", "crowd", "weather", "ticket price")
    return any(term in lowered for term in out_of_scope_terms)


def _is_nearest_question(question: str) -> bool:
    """Detects a "nearest/closest station to me"-style question - checked
    BEFORE find_stations ever runs (see answer_question) specifically
    because a real bug shipped otherwise: "what's the nearest PATH
    station to me" has no location to answer from without real
    coordinates, but "PATH" alone can still substring-match real station
    names (e.g. two real NJT bus stops literally named "PATH STATION")
    and get treated as a station-name search instead - see
    OPEN_QUESTIONS.md, 2026-08-08. With real lat/lng now provided by the
    client (see answer_question's lat/lng params), this becomes a real,
    answerable question via station_index.nearest_stations rather than
    an automatic refusal.
    """
    lowered = question.lower()
    nearest_terms = ("nearest", "closest", "near me", "close to me")
    return any(term in lowered for term in nearest_terms)


def _is_routing_question(question: str) -> bool:
    """Detects a "how do I get from A to B"/"fastest way from A to B"
    trip-planning question - checked BEFORE the plain station-name match
    below (see answer_question) for the same reason _is_nearest_question
    is: a real bug shipped otherwise. "what's the fastest way from
    Hoboken to World Trade Center" contains two real station names, so
    find_stations happily returns matches and the old pipeline silently
    answered using just ONE of them as if that addressed the whole
    question - a real hallucination found live, not a hypothetical (see
    OPEN_QUESTIONS.md, 2026-08-08). A question naming two-or-more
    stations plus one of these routing verbs is a genuinely different
    question this app either has real PATH-topology logic for
    (route_between_stations) or must refuse honestly for - never silently
    answered as if it were a single-station arrivals question.
    """
    lowered = question.lower()
    routing_terms = (
        "fastest way", "quickest way", "how do i get", "how do you get",
        "how long does it take", "how long to get", "get from", "route from",
        "way from",
    )
    return any(term in lowered for term in routing_terms)


def _is_direction_toggle_question(question: str) -> bool:
    """Detects "what about the other direction"/"the other way"-style
    follow-ups - checked BEFORE the plain station-lookup/history-fallback
    path (see answer_question) so it can specifically re-fetch and answer
    with ONLY the complementary PATH direction, rather than the LLM being
    handed every direction merged together and having to guess which
    ones count as "the other" one (a real bug found live - see
    _answer_direction_toggle's docstring).
    """
    lowered = question.lower()
    toggle_terms = ("other direction", "other way", "opposite direction", "reverse direction")
    return any(term in lowered for term in toggle_terms)


def _is_personal_question(question: str) -> bool:
    """Same cheap, auditable keyword-gate approach as _is_out_of_scope -
    not the LLM's call, since "is this asking about ME specifically" is
    exactly the kind of scope judgment that shouldn't drift silently.
    Only ever widens which questions ATTEMPT the personalized path (see
    answer_question) - never itself decides the personalized path
    succeeds; recommend_for_station's own real no-history/no-live-data
    checks still gate whether it actually returns anything.
    """
    lowered = question.lower()
    personal_terms = (
        "usual", "usually", "normally", "typically",
        "my train", "my bus", "my usual",
        "do i usually", "what do i take", "what should i take",
        "should i take",
    )
    return any(term in lowered for term in personal_terms)


async def _fetch_all_arrivals(match: StationMatch) -> ArrivalsResult:
    """Fetches every real arrival for [match]'s station across every
    route/direction that agency serves there - a chat question never
    specifies a single route/direction the way an app screen selection
    does, so nothing here may narrow to just one and call it complete.
    """
    if match.agency == "mta":
        results = [await mta.get_arrivals(match.code, route) for route in match.routes]
        return _merge(results)
    if match.agency == "path":
        results = [
            await path.get_arrivals(match.code, direction)
            for direction in ("ToNY", "ToNJ")
        ]
        return _merge(results)
    if match.agency == "njt_rail":
        return await njt_rail.get_arrivals(match.code)
    if match.agency == "lirr":
        return await lirr.get_arrivals(match.code)
    return await njt_bus.get_arrivals([match.code])


def _merge(results: list[ArrivalsResult]) -> ArrivalsResult:
    arrivals: list[Arrival] = []
    is_live = True
    for result in results:
        arrivals.extend(result.arrivals)
        is_live = is_live and result.is_live
    arrivals.sort(key=lambda a: a.arrival_time)
    return ArrivalsResult(arrivals=arrivals, is_live=is_live)


_AGENCY_TERMS: dict[str, str] = {
    "path": "path",
    "mta": "mta",
    "subway": "mta",
    "njt rail": "njt_rail",
    "nj transit rail": "njt_rail",
    "njt bus": "njt_bus",
    "nj transit bus": "njt_bus",
    "lirr": "lirr",
    "long island rail road": "lirr",
}


def _agency_mentioned(question: str) -> str | None:
    """Best-effort, cheap keyword match for which agency a "nearest ___
    station" question means (e.g. "nearest PATH station" -> "path") -
    None (search every agency) when no agency name appears, e.g. a plain
    "what's the nearest station to me". Same auditable-keyword-list
    posture as every other classifier in this module - a wrong/missing
    match here only ever widens the search, never silently narrows to
    the wrong agency and hides a closer real station in a different one.
    """
    lowered = question.lower()
    for term, agency in _AGENCY_TERMS.items():
        if term in lowered:
            return agency
    return None


# "from X to Y" is checked first since it's the far more common real
# phrasing; "to Y from X" (e.g. "how do I get to WTC from Hoboken")
# covers the reverse order - both anchored on real "from"/"to" words, not
# just splitting on any station-name pair (see the docstring below for
# why that matters).
_ROUTING_SPLIT_FROM_TO = re.compile(r"\bfrom\b(.+?)\bto\b(.+)", re.IGNORECASE)
_ROUTING_SPLIT_TO_FROM = re.compile(r"\bto\b(.+?)\bfrom\b(.+)", re.IGNORECASE)


def _extract_two_stations(question: str) -> tuple[StationMatch, StationMatch] | None:
    """Splits a routing question on its real "from X to Y" (or "to Y from
    X") structure and resolves each half independently via find_stations
    - deliberately NOT reusing find_stations on the whole question
    (that's exactly what caused the real hallucination bug: both halves'
    station names get returned together with no way to tell which one is
    the origin vs the destination). Returns None (never a guess) unless
    BOTH halves resolve to exactly one real, unambiguous PATH station
    each - a same-agency collision (e.g. "Hoboken" naming both a PATH and
    an NJT rail station), a vague reference ("from there") with no real
    station name of its own, or a station this app has no PATH-topology
    entry for all correctly fall through to a real refusal in
    _answer_routing_question, not a picked-at-random guess.
    """
    match = _ROUTING_SPLIT_FROM_TO.search(question)
    if match is not None:
        origin_text, destination_text = match.group(1), match.group(2)
    else:
        match = _ROUTING_SPLIT_TO_FROM.search(question)
        if match is None:
            return None
        destination_text, origin_text = match.group(1), match.group(2)

    origin_matches = [m for m in find_stations(origin_text) if m.agency == "path"]
    destination_matches = [m for m in find_stations(destination_text) if m.agency == "path"]
    if len(origin_matches) != 1 or len(destination_matches) != 1:
        return None
    return origin_matches[0], destination_matches[0]


async def _answer_routing_question(
    question: str, history: list[ChatMessage] | None = None
) -> ChatAnswer:
    """Answers a real "how do I get from A to B"/"fastest way from A to
    B" question - genuinely different from a plain arrivals question
    (see _is_routing_question's docstring for the real bug this replaces:
    the old pipeline silently answered using just one of the two named
    stations' arrivals). Only PATH pairs are supported today (see
    path_topology.py's module docstring for why - PATH's real topology is
    small/fixed enough to hardcode precisely; MTA/NJT would need real
    graph-search routing, not a lookup table). Every other case - a
    non-PATH pair, an ambiguous station name, or two stations PATH's own
    topology table doesn't connect - is a real, honest "route_unsupported"
    refusal, never a guessed route or invented transfer station.
    """
    stations = _extract_two_stations(question)
    if stations is None:
        context = {"kind": "route_unsupported"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    origin, destination = stations
    legs = route_between_stations(origin.code, destination.code)
    if not legs:
        context = {"kind": "route_unsupported"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    leg_contexts = []
    for leg in legs:
        result = await path.get_arrivals(leg.board_code, leg.direction)
        wait_minutes = round(result.arrivals[0].minutes_until, 1) if result.arrivals else None
        leg_contexts.append(
            {
                "route": leg.route,
                "board": station_for("path", leg.board_code).name,
                "alight": station_for("path", leg.alight_code).name,
                "wait_minutes": wait_minutes,
            }
        )

    context = {
        "kind": "route",
        "origin": origin.name,
        "destination": destination.name,
        "legs": leg_contexts,
    }
    text = _ask_llm(question, context, history) or _template_answer(context)
    return ChatAnswer(text=text, station=destination)


async def _answer_direction_toggle(
    question: str, history: list[ChatMessage] | None = None
) -> ChatAnswer:
    """Answers "what about the other direction"/"the other way" - a real
    bug found live: the old pipeline just re-fetched EVERY direction
    merged together (same as any plain arrivals question) and handed the
    LLM headsigns it had no real way to split into "the one already
    discussed" vs "the other one," so it either repeated the same
    answer or invented a distinction. Fixed by actually filtering real
    arrivals to whichever headsigns were NOT shown last time (see
    _last_shown_headsigns) - never guessing which direction is "other."
    Refuses honestly (no real prior single-direction answer to invert,
    or the filtered set comes back empty - e.g. this station only ever
    has one real headsign) rather than falling back to the ambiguous
    merged-everything answer this bug started from.
    """
    history = history or []
    station = _last_mentioned_station(history)
    shown = _last_shown_headsigns(history)
    if station is None or shown is None:
        context = {"kind": "no_match"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    result = await _fetch_all_arrivals(station)
    other_direction_arrivals = [
        a for a in result.arrivals if a.headsign and a.headsign not in shown
    ]
    if not other_direction_arrivals:
        context = {"kind": "no_match"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    context = {
        "kind": "arrivals",
        "station": station.name,
        "agency": station.agency,
        "arrivals": [
            {
                "route_label": a.route_label,
                "minutes_until": round(a.minutes_until, 1),
                "headsign": a.headsign,
            }
            for a in other_direction_arrivals[:_MAX_ARRIVALS_IN_ANSWER]
        ],
        "is_live": result.is_live,
    }
    text = _ask_llm(question, context, history) or _template_answer(context)
    # Same "soonest arrival only" posture as _answer_for_match - a
    # follow-up "and the other way again" after THIS answer must invert
    # relative to what was just shown, not the full filtered set.
    soonest = other_direction_arrivals[0]
    new_headsigns = frozenset({soonest.headsign}) if soonest.headsign else None
    return ChatAnswer(text=text, station=station, headsigns=new_headsigns)


def _answer_nearest_question(
    question: str,
    lat: float | None,
    lng: float | None,
    history: list[ChatMessage] | None = None,
) -> ChatAnswer:
    """Answers a "nearest/closest station to me" question using the
    client's real coordinates - see answer_question's lat/lng docs and
    station_index.nearest_stations. Never invents a station or a
    distance: no coordinates provided (the common case - most callers
    don't have location permission, or the question isn't asking about
    location at all) is a real, honest refusal, not a guess. Answers
    with the station's name and real distance only - not its live
    arrivals; a natural follow-up question ("what time's the next train
    from there") re-enters the normal stateless pipeline above using the
    real station name this answer already gave.
    """
    if lat is None or lng is None:
        context = {"kind": "no_location"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    agency = _agency_mentioned(question)
    nearby = nearest_stations(lat, lng, limit=1, agency=agency)
    if not nearby:
        context = {"kind": "no_location"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    nearest = nearby[0]
    context = {
        "kind": "nearest",
        "station": nearest.station.name,
        "agency": nearest.station.agency,
        "distance_miles": round(nearest.distance_miles, 1),
    }
    text = _ask_llm(question, context, history) or _template_answer(context)
    return ChatAnswer(text=text, station=nearest.station)


def _load_recent_history(db: Session, session_id: uuid.UUID) -> list[ChatMessage]:
    """The session's real last _MAX_HISTORY_TURNS turns, oldest first -
    a plain read of what was actually said (see the module docstring's
    "never re-derive history" note), never a summary or guess.
    """
    rows = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id.desc())
        .limit(_MAX_HISTORY_TURNS)
    ).all()
    return list(reversed(rows))


def _last_mentioned_station(history: list[ChatMessage]) -> StationMatch | None:
    """The most recent real station an assistant turn in this session
    actually resolved to - what a station-less follow-up ("what about
    the other direction", "what time's the next one") falls back to
    instead of failing with "no match." Walks newest-first; None if no
    turn in the given history ever landed on a real station (never
    invents one).
    """
    for turn in reversed(history):
        if turn.role == "assistant" and turn.station_agency and turn.station_code:
            match = station_for(turn.station_agency, turn.station_code)
            if match is not None:
                return match
    return None


def _last_shown_headsigns(history: list[ChatMessage]) -> set[str] | None:
    """The real destination(s) the most recent assistant turn recorded as
    "shown" - see _save_turn's [headsigns] param. Deliberately just the
    SOONEST arrival's real headsign, not every direction merged together
    (a plain "what's next" answer always fetches every real direction at
    once - see _fetch_all_arrivals's docstring - so if this recorded
    every headsign shown, "the other direction" would always find
    nothing left to be "other," since everything was already "shown."
    What a user actually means by "the other direction" is "not the one
    you just told me about" - i.e. not the SOONEST arrival's real
    destination, which is what chat_ai._answer_for_match actually records
    (see its shown= computation). None if the last real answer had no
    headsign data at all (a non-PATH station, or a refusal/ambiguous/etc
    turn) - that case correctly falls through to a real refusal instead
    of guessing.
    """
    for turn in reversed(history):
        if turn.role == "assistant" and turn.shown_headsigns:
            return set(turn.shown_headsigns.split(","))
    return None


def _save_turn(
    db: Session,
    session_id: uuid.UUID,
    role: str,
    content: str,
    station: StationMatch | None = None,
    headsigns: frozenset[str] | None = None,
) -> None:
    db.add(
        ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            station_agency=station.agency if station else None,
            station_code=station.code if station else None,
            shown_headsigns=",".join(sorted(headsigns)) if headsigns else None,
        )
    )
    db.commit()


def _ensure_session(db: Session, session_id: uuid.UUID, user_id=None) -> None:
    """Creates the session row on its first real message if it doesn't
    exist yet - the client mints the id (see the module docstring), so
    the backend never needs to hand one out; this just makes sure a
    matching row exists to hang messages off before the first insert.
    """
    existing = db.get(ChatSession, session_id)
    if existing is None:
        db.add(ChatSession(id=session_id, user_id=user_id))
        db.commit()


async def answer_question(
    question: str,
    db: Session | None = None,
    user_id=None,
    lat: float | None = None,
    lng: float | None = None,
    session_id: uuid.UUID | None = None,
) -> ChatAnswer:
    """[db]/[user_id] are only used for the personalized tier - both None
    (the stateless caller's default) means "never attempt personalization,"
    same behavior as before this tier existed. A caller passing user_id
    without a real db session (or vice versa) is a programming error, not
    handled specially - both are set together by the router or neither is.

    [lat]/[lng] are the caller's real device coordinates, if the client
    both has location permission AND sent them (see routers/chat.py) -
    used only for a "nearest station" question (see _is_nearest_question);
    ignored entirely for every other question. Both None (no coordinates
    sent, or the question isn't location-dependent) is the normal case
    for most questions and callers.

    [session_id] is the client-generated conversation id (see the module
    docstring's "real conversation memory" section) - None (the default,
    matching every call site before this existed, e.g. direct test calls)
    means no history is loaded or saved, same single-turn behavior as
    before. A real UUID with a real [db] session both loads this
    conversation's recent turns for the LLM and persists this new
    question+answer as the next turn.
    """
    history = (
        _load_recent_history(db, session_id) if db is not None and session_id else []
    )

    if _is_conversation_closer(question):
        # A plain "ok thanks"/"got it" isn't a question at all - never
        # sent to the LLM (nothing to phrase, and a real bug found live:
        # this used to fall through to the no-real-station-yet path and
        # get answered as if it were a genuine clarification request).
        # A fixed, friendly reply is correct every time, at zero cost.
        answer = ChatAnswer(text="You're welcome! Let me know if you need anything else.", station=None)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    if _is_nearest_question(question):
        answer = _answer_nearest_question(question, lat, lng, history)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    if _is_routing_question(question):
        answer = await _answer_routing_question(question, history)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    if _is_direction_toggle_question(question):
        answer = await _answer_direction_toggle(question, history)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    if _is_out_of_scope(question):
        context = {"kind": "out_of_scope"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        answer = ChatAnswer(text=text, station=None)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    matches = find_stations(question)

    if not matches:
        # No station name in THIS question - a real prior turn in this
        # same conversation may still resolve it (e.g. "what time's the
        # next one" right after asking about a specific station). Only
        # ever falls back to a station this session's own history
        # actually named, never a guess synthesized from the question.
        fallback = _last_mentioned_station(history)
        if fallback is not None:
            answer = await _answer_for_match(question, fallback, db, user_id, history)
            _persist_turn(db, session_id, user_id, question, answer)
            return answer

        context = {"kind": "no_match"}
        text = _ask_llm(question, context, history) or _template_answer(context)
        answer = ChatAnswer(text=text, station=None)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    if not _is_unambiguous(question, matches):
        context = {
            "kind": "ambiguous",
            "options": [
                {"name": m.name, "agency": m.agency, "toward": m.toward} for m in matches
            ],
        }
        text = _ask_llm(question, context, history) or _template_answer(context)
        answer = ChatAnswer(text=text, station=None)
        _persist_turn(db, session_id, user_id, question, answer)
        return answer

    match = matches[0]
    answer = await _answer_for_match(question, match, db, user_id, history)
    _persist_turn(db, session_id, user_id, question, answer)
    return answer


async def _answer_for_match(
    question: str,
    match: StationMatch,
    db: Session | None,
    user_id,
    history: list[ChatMessage],
) -> ChatAnswer:
    """The shared "we have one real unambiguous station, now answer"
    tail of the pipeline - factored out so both a question that names its
    own station and a station-less follow-up resolved via
    _last_mentioned_station go through the exact same personalized/
    stateless logic, not two copies of it.
    """
    if db is not None and user_id is not None and _is_personal_question(question):
        personalized = await _try_personalized_answer(db, user_id, match)
        if personalized is not None:
            return personalized
        # Falls through to the stateless path below - a personal-sounding
        # question from a logged-in user with no history/live data yet
        # still gets a real, useful (just not personalized) answer rather
        # than an empty result.

    result = await _fetch_all_arrivals(match)
    context = {
        "kind": "arrivals",
        "station": match.name,
        "agency": match.agency,
        "arrivals": [
            {
                "route_label": a.route_label,
                "minutes_until": round(a.minutes_until, 1),
                # Real per-arrival destination when the source feed
                # reports one (PATH does; MTA's GTFS-RT never does) - see
                # transit/models.py's Arrival.headsign docstring. Omitted
                # entirely (never a fabricated placeholder) when the feed
                # gave none for this specific arrival.
                **({"headsign": a.headsign} if a.headsign else {}),
            }
            for a in result.arrivals[:_MAX_ARRIVALS_IN_ANSWER]
        ],
        "is_live": result.is_live,
    }
    text = _ask_llm(question, context, history) or _template_answer(context)
    # Deliberately only the SOONEST arrival's real headsign, not every
    # direction merged together - see _last_shown_headsigns's docstring
    # for why recording everything shown here would make "the other
    # direction" always find nothing left to be "other." The soonest
    # arrival is what a user's attention actually lands on when reading
    # "the next arrival at X is toward Y."
    soonest = result.arrivals[0] if result.arrivals else None
    shown = frozenset({soonest.headsign}) if soonest and soonest.headsign else None
    return ChatAnswer(text=text, station=match, headsigns=shown)


def _persist_turn(
    db: Session | None,
    session_id: uuid.UUID | None,
    user_id,
    question: str,
    answer: ChatAnswer,
) -> None:
    """Saves this real question+answer as the conversation's next two
    turns - a no-op when there's no session to attach them to (session_id
    is None, e.g. every call site/test that predates conversation memory)
    so this never becomes a hard requirement for answering a question.
    """
    if db is None or session_id is None:
        return
    _ensure_session(db, session_id, user_id)
    _save_turn(db, session_id, "user", question)
    _save_turn(db, session_id, "assistant", answer.text, answer.station, answer.headsigns)


async def _try_personalized_answer(db: Session, user_id, match: StationMatch) -> ChatAnswer | None:
    """Calls the EXACT SAME function Commute AI's own GET /commute
    endpoint calls, with the user's real reliability_pref, phrased with
    the EXACT SAME phrase_commute_recommendation - see the module
    docstring on why this, not a second implementation, is what makes
    the PRD's "must give the same answer Commute AI would give in card
    form" requirement true by construction rather than a promise to keep
    two copies in sync.
    """
    user = db.get(User, user_id)
    if user is None:
        return None

    recommendation = await recommend_for_station(
        db, user_id, match.agency, match.code, user.reliability_pref
    )
    if recommendation is None:
        return None

    text = phrase_commute_recommendation(recommendation)
    return ChatAnswer(text=text, station=match)


def _is_unambiguous(question: str, matches: list[StationMatch]) -> bool:
    """A query can substring-match many rows (e.g. "hoboken" matches both
    the real Hoboken PATH/NJT-rail station AND several unrelated NJT bus
    stops with "Hoboken Ave" in their street name) while still having one
    clearly-intended winner - the shortest/closest name match. Treat that
    as unambiguous only when the top match's name is a genuine whole-word
    match within the question (same contains_whole check find_stations
    itself uses - a full free-text question is never literally EQUAL to a
    bare station name, so checking exact equality here was a real bug:
    it silently treated every real full-sentence question as ambiguous,
    only ever "working" in tests/usage that happened to pass a bare
    station name) AND no other match shares that exact same name -
    several of MTA's real stations share an exact name despite being
    unconnected, unrelated physical stations (e.g. four separate "23 St"s
    - see OPEN_QUESTIONS.md), so a genuine name match alone isn't enough
    to safely pick one; this must still surface real options rather than
    silently guessing among them.
    """
    top = matches[0]
    normalized_question = normalize(question)
    if not contains_whole(normalized_question, normalize(top.name)):
        return False
    return not any(m is not top and normalize(m.name) == normalize(top.name) for m in matches)
