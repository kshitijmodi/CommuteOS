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
   Zero matches -> ask the user to clarify (real refusal, not a guess).
   Multiple matches -> list the real options, let the user pick.
2. A personal question, a logged-in user, and an unambiguous match ->
   try the personalized path first (see above). Anything else, or that
   path coming back empty -> the stateless path: fetch REAL live arrivals
   across every route/direction that agency's station serves (never a
   single arbitrarily-picked route/direction - a chat question doesn't
   specify one the way an app screen selection would).
3. Phrase the real fetched data into an answer. The LLM's job is exactly
   as narrow as llm_phrasing.py's: turn real structured data into a
   sentence, never invent a number, never answer a question with no real
   data behind it (fares, crowding, anything outside NYC-metro transit) -
   it must refuse those plainly instead of guessing.
"""

from dataclasses import dataclass

from openai import OpenAI, OpenAIError
from sqlalchemy.orm import Session

from .commute_engine import recommend_for_station
from .core.config import settings
from .llm_phrasing import phrase_commute_recommendation
from .models import User
from .station_index import (
    StationMatch,
    contains_whole,
    find_stations,
    nearest_stations,
    normalize,
)
from .transit import lirr, mta, njt_bus, njt_rail, path
from .transit.models import Arrival, ArrivalsResult

_MAX_ARRIVALS_IN_ANSWER = 5

_SYSTEM_PROMPT = """You are CommuteOS's transit chat assistant, scoped \
strictly to NYC-metro subway/rail/bus arrival times (MTA, PATH, NJ \
Transit rail and bus, LIRR).

You will be given a JSON object with the user's question and a "context" \
field. The context is one of:
- {"kind": "arrivals", "station": ..., "agency": ..., "arrivals": [...]} \
- real live arrival data already fetched for the station the question \
named. Answer using ONLY these numbers.
- {"kind": "no_match"} - no known station matched the question. Ask the \
user to clarify which station they mean; do not guess one.
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

Rules you must never break:
- Never invent a time, a station, or a fact not present in the given \
context.
- If context.kind is "arrivals" but the arrivals list is empty, say so \
plainly (no service found right now) rather than inventing a time.
- Keep the answer to 1-3 short sentences, natural and direct.
- Output only the answer text, no preamble, no quotes around it."""


@dataclass(frozen=True)
class ChatAnswer:
    text: str
    station: StationMatch | None


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

    arrivals = context["arrivals"]
    station = context["station"]
    if not arrivals:
        return f"No upcoming arrivals found for {station} right now."
    soonest = arrivals[0]
    return f"The next arrival at {station} is {soonest['route_label']} in about {soonest['minutes_until']} min."


def _ask_llm(question: str, context: dict) -> str | None:
    if not settings.groq_api_key:
        return None

    client = OpenAI(api_key=settings.groq_api_key, base_url="https://api.groq.com/openai/v1")
    payload = {"question": question, "context": context}

    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            temperature=0.2,
            max_tokens=200,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": str(payload)},
            ],
        )
        text = response.choices[0].message.content
        return text.strip() if text else None
    except OpenAIError:
        return None


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


def _answer_nearest_question(
    question: str, lat: float | None, lng: float | None
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
        text = _ask_llm(question, context) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    agency = _agency_mentioned(question)
    nearby = nearest_stations(lat, lng, limit=1, agency=agency)
    if not nearby:
        context = {"kind": "no_location"}
        text = _ask_llm(question, context) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    nearest = nearby[0]
    context = {
        "kind": "nearest",
        "station": nearest.station.name,
        "agency": nearest.station.agency,
        "distance_miles": round(nearest.distance_miles, 1),
    }
    text = _ask_llm(question, context) or _template_answer(context)
    return ChatAnswer(text=text, station=nearest.station)


async def answer_question(
    question: str,
    db: Session | None = None,
    user_id=None,
    lat: float | None = None,
    lng: float | None = None,
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
    """
    if _is_nearest_question(question):
        return _answer_nearest_question(question, lat, lng)

    if _is_out_of_scope(question):
        context = {"kind": "out_of_scope"}
        text = _ask_llm(question, context) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    matches = find_stations(question)

    if not matches:
        context = {"kind": "no_match"}
        text = _ask_llm(question, context) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    if not _is_unambiguous(question, matches):
        context = {
            "kind": "ambiguous",
            "options": [
                {"name": m.name, "agency": m.agency, "toward": m.toward} for m in matches
            ],
        }
        text = _ask_llm(question, context) or _template_answer(context)
        return ChatAnswer(text=text, station=None)

    match = matches[0]

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
            }
            for a in result.arrivals[:_MAX_ARRIVALS_IN_ANSWER]
        ],
        "is_live": result.is_live,
    }
    text = _ask_llm(question, context) or _template_answer(context)
    return ChatAnswer(text=text, station=match)


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
