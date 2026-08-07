"""Loads app/data/chat_station_index.csv (see
backend/scripts/build_chat_station_index.py for how it's built) and
resolves a free-text station name from a chat question into real
(agency, code) matches - the one thing Chat AI's stateless tier needs
that nothing else in the backend has, since every other feature either
gets a station code directly from the client (recommendations) or from
Trip history (home/office inference), never from unstructured text.

Deliberately simple matching (normalize + substring), not embeddings/
fuzzy-distance search - station names are a small, fixed vocabulary
(~5,900 rows) and a user asking about "hoboken" or "what's next from
grove street" is well served by checking whether a station's name
appears as a real word-boundary-respecting substring of the question;
embedding search would add a real dependency and latency for no accuracy
gain at this vocabulary size.
"""

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources


@dataclass(frozen=True)
class StationMatch:
    name: str
    agency: str  # "mta" | "path" | "njt_rail" | "njt_bus" | "lirr"
    code: str
    # MTA only - the route IDs serving this station (e.g. ["N", "W"]),
    # needed because mta.get_arrivals requires one route_id per call, and
    # nothing about a chat question specifies a route. Empty for every
    # other agency (their get_arrivals only needs a station/stop code).
    routes: list[str]


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
            stations.append(
                StationMatch(
                    name=record["name"],
                    agency=record["agency"],
                    code=record["code"],
                    routes=routes,
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
        if _contains_whole(normalized_query, normalize(station.name))
    ]
    matches.sort(key=lambda s: len(s.name))
    return matches[:limit]


def _contains_whole(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return re.search(rf"(?<!\w){re.escape(needle)}(?!\w)", haystack) is not None
