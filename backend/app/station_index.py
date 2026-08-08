"""Loads app/data/chat_station_index.csv (see
backend/scripts/build_chat_station_index.py for how it's built). Two
callers, two lookups:

- Chat AI's stateless tier (find_stations) resolves a free-text station
  name from a chat question into real (agency, code) matches - the one
  thing that feature needs that nothing else in the backend has, since
  every other feature either gets a station code directly from the
  client (recommendations) or from Trip history (home/office inference),
  never from unstructured text.
- Commute AI (station_for) looks up a station's own real candidate set
  (routes/directions) given an (agency, code) it already knows - see
  StationMatch.routes's docstring.

find_stations's matching is deliberately simple (normalize + substring),
not embeddings/fuzzy-distance search - station names are a small, fixed
vocabulary (~5,900 rows) and a user asking about "hoboken" or "what's
next from grove street" is well served by checking whether a station's
name appears as a real word-boundary-respecting substring of the
question; embedding search would add a real dependency and latency for
no accuracy gain at this vocabulary size.
"""

import csv
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

# Mean Earth radius in miles - used by nearest_stations's haversine
# distance calculation. A sphere, not an ellipsoid, is plenty accurate
# for "which station is closest" at NYC-metro distances (a few miles at
# most) - the ellipsoid-vs-sphere error is on the order of tenths of a
# percent, far smaller than GPS's own real-world accuracy.
_EARTH_RADIUS_MILES = 3958.8


@dataclass(frozen=True)
class StationMatch:
    name: str
    agency: str  # "mta" | "path" | "njt_rail" | "njt_bus" | "lirr"
    code: str
    # MTA/PATH only - every real route_or_direction get_arrivals can be
    # called with for this station (MTA: subway routes, e.g. ["N", "W"];
    # PATH: its two fixed direction keys, ["ToNY", "ToNJ"]) - needed
    # because both agencies require one route_or_direction per fetch call,
    # unlike NJT rail/bus/LIRR where a station code alone is enough (empty
    # list for those). Originally added for Chat AI (nothing about a chat
    # question specifies a route); Commute AI (commute_engine.py) reads
    # this as the station's full candidate set to rank.
    routes: list[str]
    # NJT bus only - a real "toward <terminus>" hint (same data the
    # Flutter station picker already shows, see NjtBusStop.toward), when
    # one exists for this stop_id. None for every other agency, and for
    # NJT bus stops with no clear single direction (e.g. a merged multi-
    # bay terminal). Exists so chat_ai.py can actually distinguish two
    # real, different stops that happen to share an exact name (e.g. two
    # separate "PATH STATION" stop_ids on opposite sides of a real
    # intersection) instead of presenting two options that render
    # identically - a real bug found live, see OPEN_QUESTIONS.md.
    toward: str | None = None
    # Real coordinates for every station in the index (added 2026-08-08
    # for "nearest station to me" - see nearest_stations). None only if a
    # row's lat/lng genuinely failed to parse, which should not happen
    # for any real row in the index - treated as "cannot be used for a
    # distance calculation," never defaulted to 0.0/0.0 (a real place on
    # Earth, not a safe stand-in for "unknown").
    lat: float | None = None
    lng: float | None = None


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


@lru_cache(maxsize=1)
def _all_stations() -> list[StationMatch]:
    stations = []
    with resources.files("app.data").joinpath("chat_station_index.csv").open(
        "r", encoding="utf-8"
    ) as f:
        for record in csv.DictReader(f):
            routes = [r for r in record["routes"].split("|") if r]
            toward = record.get("toward") or None
            lat = _parse_float(record.get("lat"))
            lng = _parse_float(record.get("lng"))
            stations.append(
                StationMatch(
                    name=record["name"],
                    agency=record["agency"],
                    code=record["code"],
                    routes=routes,
                    toward=toward,
                    lat=lat,
                    lng=lng,
                )
            )
    return stations


def find_stations(query: str, limit: int = 5) -> list[StationMatch]:
    """Returns every station whose name appears as a whole-word substring
    of [query] (case/punctuation-insensitive) - so both a bare station
    name ("Hoboken") and a full free-text question ("what's the next PATH
    train from Hoboken") match the same way, since the question always
    contains the station name as a substring, never the reverse. Sorted
    shortest-name-first, so a short exact-ish name (e.g. "Hoboken") ranks
    above a long incidental substring match (e.g. "Hoboken Ave at Summit
    Ave"). Word-boundary-anchored so a short station name/code doesn't
    match as a fragment inside an unrelated word (e.g. a station named
    "Ave" shouldn't match every question containing "avenue"). Empty list
    (never a guess) if nothing matches - callers must ask the user to
    clarify rather than picking an arbitrary station.
    """
    normalized_query = normalize(query)
    if not normalized_query:
        return []

    matches = [
        station
        for station in _all_stations()
        if contains_whole(normalized_query, normalize(station.name))
    ]
    matches.sort(key=lambda s: len(s.name))
    return matches[:limit]


def contains_whole(haystack: str, needle: str) -> bool:
    """Public (not just find_stations's private helper) since chat_ai.py's
    _is_unambiguous needs the same whole-word-substring check to decide
    "does this match's name genuinely appear in the question," not just
    "is the whole question equal to the name" - a full free-text question
    is never literally equal to a bare station name.
    """
    if not needle:
        return False
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None


def station_for(agency: str, code: str) -> StationMatch | None:
    """Exact (agency, code) lookup - what Commute AI uses, since it's
    called with a station the client already identified (opening that
    station's arrivals screen), never resolving free text. None if the
    agency/code pair isn't in the index (never a guess) - callers must
    treat this the same as "no candidate set known for this station."
    """
    for station in _all_stations():
        if station.agency == agency and station.code == code:
            return station
    return None


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


@dataclass(frozen=True)
class NearbyStation:
    station: StationMatch
    distance_miles: float


def nearest_stations(
    lat: float, lng: float, limit: int = 3, agency: str | None = None
) -> list[NearbyStation]:
    """Real haversine great-circle distance from (lat, lng) to every
    station in the index that actually has real coordinates (see
    StationMatch.lat/lng's docstring - a station with no parsed
    coordinate is silently excluded here, never treated as
    distance-zero). Sorted nearest-first. [agency] optionally narrows to
    one agency (e.g. "path" for "nearest PATH station") - None searches
    every agency. Empty list (never a guess) if nothing in scope has
    real coordinates to compare against.
    """
    candidates = [s for s in _all_stations() if s.lat is not None and s.lng is not None]
    if agency is not None:
        candidates = [s for s in candidates if s.agency == agency]

    results = [
        NearbyStation(station=s, distance_miles=_haversine_miles(lat, lng, s.lat, s.lng))
        for s in candidates
    ]
    results.sort(key=lambda r: r.distance_miles)
    return results[:limit]


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_r, lng1_r, lat2_r, lng2_r = map(math.radians, (lat1, lng1, lat2, lng2))
    delta_lat = lat2_r - lat1_r
    delta_lng = lng2_r - lng1_r
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return _EARTH_RADIUS_MILES * c
