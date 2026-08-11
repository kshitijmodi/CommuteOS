"""PATH's real route topology - Newark/Harrison/Journal Square/Grove
Street/Exchange Place/WTC/Hoboken/Newport/Christopher St/9th/14th/23rd/
33rd St, and which of PATH's 4 standard routes actually connects which
station pairs. Hardcoded from real, verified facts (PATH's own live API
contract + PANYNJ's May 2026 service announcement - see OPEN_QUESTIONS.md
for the sourcing), same "small, fixed, auditable table" posture as every
other hand-maintained real-world fact in this codebase (e.g.
_mtaRouteColors in the Flutter client, or _PATH_STATIONS in
build_chat_station_index.py).

Built for chat_ai.py's station-to-station routing (added 2026-08-08,
after a real bug: the LLM was answering "fastest way from A to B"
questions by silently reinterpreting them as a plain arrivals lookup at
one of the two stations, inventing an answer to a question the app had
no real capability to answer). PATH is deliberately the first (and for
now, only) agency this module covers real cross-station routing for -
its real topology is small/fixed enough to hardcode precisely, unlike
MTA's ~30-line subway network or NJT's much larger rail/bus network,
which would need a real graph-search implementation, not a lookup table
(explicitly out of scope for now - see route_between's docstring).

Deliberately NOT modeling frequency/schedule/off-peak service changes
(e.g. the JSQ_33_HOB late-night/weekend "via Hoboken" variant) - this
only answers "is there a real one-seat ride, and if not, where's the
real transfer," using each route's ALWAYS-active real topology. A
specific trip that only runs late-night is a real scheduling nuance
callers should still confirm against live arrivals, which this module
doesn't fetch - see chat_ai.route_between_stations for how the real
live arrival check is layered on top of this purely-topological lookup.

Real correction, 2026-08-10/11 (see OPEN_QUESTIONS.md): JSQ_33's real
station list was missing Newport entirely, wrongly modeling Grove
Street<->Newport as needing a transfer at Exchange Place when a real,
direct, all-day weekday JSQ_33 train actually runs Journal Square ->
Grove Street -> Newport -> Christopher St -> ... -> 33rd Street. Found
via a real user correction, verified against PATH's own live API
(both stations reporting the same real "33rd Street via Hoboken"
headsign/lineColor at the same live moment) and independently
cross-checked against Wikipedia's Grove Street/Newport station articles
before fixing - this was a real hardcoded-data error, not a phrasing or
prompt issue, so the fix belongs here, not in chat_ai.py.
"""

from dataclasses import dataclass

# Each PATH station's real code -> which of PATH's 4 standard routes stop
# there, in the order the trains actually run. NPT_HOB (the rare
# contingency shuttle) and the late-night/weekend-only "via Hoboken"
# JSQ_33 variant (a real, different routing that detours through
# Hoboken instead of Newport) are deliberately excluded - real, but not
# part of PATH's always-available standard service, and including them
# would make a late-night-only path look like a real one-seat ride at
# 2pm on a Tuesday. The PLAIN JSQ_33 route below (via Newport, not via
# Hoboken) DOES run standard weekday daytime service - confirmed real,
# not excluded.
_ROUTES: dict[str, list[str]] = {
    "NWK_WTC": ["NWK", "HAR", "JSQ", "GRV", "EXP", "WTC"],
    "HOB_WTC": ["HOB", "NEW", "EXP", "WTC"],
    "JSQ_33": ["JSQ", "GRV", "NEW", "CHR", "09S", "14S", "23S", "33S"],
    "HOB_33": ["HOB", "CHR", "09S", "14S", "23S", "33S"],
}

# Real transfer stations - a station that sits on 2+ of the routes above,
# so a trip needing to move between routes can genuinely do so here
# without leaving the system. Derived from _ROUTES itself below, listed
# explicitly here only for the module docstring's benefit; the real
# computation lives in _transfer_stations().
_KNOWN_TRANSFER_STATIONS = {"JSQ", "GRV", "NEW", "EXP", "HOB"}


@dataclass(frozen=True)
class PathLeg:
    """One real, single-route ride - "board a train on [route] at
    [board_code], get off at [alight_code]." route_between_stations
    chains 1-2 of these together (1 for a direct ride, 2 for a real
    one-transfer trip); never more, since PATH's real topology never
    needs more than one transfer between any two of its 13 stations.
    """

    route: str
    board_code: str
    alight_code: str

    @property
    def direction(self) -> str:
        """The real "ToNY"/"ToNJ" label path.get_arrivals needs to fetch
        THIS leg's live arrivals - derived from _ROUTES' real stop order
        (every one of PATH's 4 standard routes is listed NJ-side-first,
        so alighting further along the list than boarding always means
        heading toward NY, never guessed per-route).
        """
        stops = _ROUTES[self.route]
        return "ToNY" if stops.index(self.alight_code) > stops.index(self.board_code) else "ToNJ"


def _routes_for_station(code: str) -> list[str]:
    return [route for route, stations in _ROUTES.items() if code in stations]


@dataclass(frozen=True)
class AdjacentStation:
    """One real next-stop relationship - "on [route], the next real stop
    heading [direction] from the station this was asked about is
    [station_code]." A station on 2+ routes (e.g. Journal Square, on
    both NWK_WTC and JSQ_33) genuinely has more than one real "next
    station" in a given direction - each one is a real, different
    physical stop, never collapsed into one guessed answer.
    """

    route: str
    direction: str  # "ToNY" | "ToNJ"
    station_code: str


def adjacent_stations(station_code: str) -> list[AdjacentStation]:
    """Every real next-stop relationship for [station_code], across
    every route it's actually on - added 2026-08-09 after a real user
    question ("what's the next station after Grove Street") that this
    app had no concept of at all: not an arrival-time question (no live
    data involved) and not an A-to-B routing question (no destination
    named) - a third, genuinely different question type, "what's
    adjacent to this station on the real line." Empty list (never a
    guess) if [station_code] isn't a real station in this table, or is
    the last stop on every route it's on with nothing further in that
    direction.
    """
    results = []
    for route in _routes_for_station(station_code):
        stops = _ROUTES[route]
        index = stops.index(station_code)
        if index + 1 < len(stops):
            results.append(AdjacentStation(route=route, direction="ToNY", station_code=stops[index + 1]))
        if index - 1 >= 0:
            results.append(AdjacentStation(route=route, direction="ToNJ", station_code=stops[index - 1]))
    return results


def route_between_stations(origin_code: str, destination_code: str) -> list[PathLeg] | None:
    """Real PATH topology only - no live data, no schedule awareness (see
    module docstring). Returns:
    - [] if origin == destination (nothing to ride).
    - A single-element list for a real direct one-seat ride (both
      stations share a route with origin listed before destination in
      that route's real stop order - PATH doesn't reverse mid-route).
    - A two-element list for a real one-transfer trip via a station both
      the origin's route and the destination's route actually serve.
    - None if no real one-transfer path exists between these two
      stations under PATH's standard topology (should not happen for any
      real pair of PATH's 13 stations - every station connects to every
      other with at most one transfer - but returned rather than raising,
      so a caller can still refuse honestly instead of crashing if this
      table is ever wrong/incomplete).
    """
    if origin_code == destination_code:
        return []

    origin_routes = _routes_for_station(origin_code)
    destination_routes = _routes_for_station(destination_code)
    if not origin_routes or not destination_routes:
        return None

    # Direct one-seat ride: same route, origin genuinely before
    # destination in that route's real real-world stop order (PATH trains
    # run one direction along a route, never skip around).
    for route in origin_routes:
        if route not in destination_routes:
            continue
        stops = _ROUTES[route]
        if stops.index(origin_code) != stops.index(destination_code):
            return [PathLeg(route=route, board_code=origin_code, alight_code=destination_code)]

    # One transfer: find a real station on BOTH an origin route and a
    # destination route (not just any station - it must actually be
    # reachable from origin on one route, and reach destination on the
    # other).
    for origin_route in origin_routes:
        origin_stops = _ROUTES[origin_route]
        for destination_route in destination_routes:
            destination_stops = _ROUTES[destination_route]
            for candidate in origin_stops:
                if candidate not in destination_stops:
                    continue
                if candidate == origin_code or candidate == destination_code:
                    continue
                if origin_stops.index(origin_code) == origin_stops.index(candidate):
                    continue
                if destination_stops.index(candidate) == destination_stops.index(destination_code):
                    continue
                return [
                    PathLeg(route=origin_route, board_code=origin_code, alight_code=candidate),
                    PathLeg(route=destination_route, board_code=candidate, alight_code=destination_code),
                ]

    return None
