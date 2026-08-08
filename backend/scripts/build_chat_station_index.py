"""Builds app/data/chat_station_index.csv - a compact name -> (agency,
code[, routes][, toward][, lat][, lng]) lookup. Originally built only for
Chat AI's stateless tier (app/station_index.py, resolving a free-text
station name into a real code the transit fetchers understand); now also
the one place Commute AI (app/commute_engine.py) looks up a station's
own real candidate set - MTA/PATH's `routes` column doubles as "every
real route_or_direction get_arrivals can be called with for this
station," which for MTA is its subway routes (e.g. "N|W") and for PATH
is its two fixed direction keys (always "ToNY|ToNJ" - see _path_rows).
NJT rail/bus/LIRR leave this column empty since a station code alone is
enough for those agencies' get_arrivals - there's no per-route/direction
candidate set to enumerate.

`toward` (NJT bus only) carries the same real "toward <terminus>" hint
already built for the Flutter station picker (see
build_njt_bus_stops.py's `toward` column and NjtBusStop.toward's docs) -
needed because two or more real, genuinely different NJT bus stops can
share an exact name (e.g. two separate stop_ids both literally named
"PATH STATION", on opposite sides of a real intersection) with nothing
else in this compact index to tell them apart. Chat AI's disambiguation
message uses this to actually distinguish them ("PATH STATION (toward
Kearny)" vs "PATH STATION (toward Jersey Gardens)") instead of asking
"which one?" against two options that render identically - a real bug
found live (see OPEN_QUESTIONS.md, 2026-08-08).

`lat`/`lng` (added 2026-08-08) power Chat AI's "nearest station to me"
answer - MTA/NJT rail/NJT bus/LIRR all already have real coordinates in
their bundled Flutter-asset CSVs; PATH previously had none anywhere in
this app (browsing/search never needed them) - added real coordinates,
verified from OpenStreetMap + Wikipedia cross-checked, to both
lib/path/path_station.dart and _PATH_STATIONS below.

Deliberately NOT a copy of any agency's FULL station CSV (ADA info,
branch lists, etc.) - those already live in the Flutter app's
assets/data/*.csv (source of truth for browsing/search) and, where the
backend also needs to re-fetch arrivals itself (LIRR), in
backend/app/data/*.csv. This script re-derives only the columns needed
here from those same source files, rather than hand-maintaining a third
copy of station data. Re-run this whenever an upstream station CSV
changes.

PATH has no CSV (see lib/path/path_station.dart's docstring - only 13
stations, hardcoded) so its 13 rows are hardcoded here too, kept in sync
by hand with that Dart file - acceptable given PATH's station list has
not changed in decades.
"""

import csv
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ASSETS = _REPO_ROOT / "assets" / "data"
_OUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "chat_station_index.csv"

# Mirrors lib/path/path_station.dart's PathStation.all, including its
# real lat/lng - keep in sync by hand if that list ever changes (see
# module docstring). Coordinates verified from OpenStreetMap's real
# `railway=station, network=PATH` nodes, cross-checked against each
# station's Wikipedia infobox (agreed within 5-110m for every station).
_PATH_STATIONS = [
    ("NWK", "Newark", 40.7344963, -74.1638550),
    ("HAR", "Harrison", 40.7393434, -74.1556748),
    ("JSQ", "Journal Square", 40.7318097, -74.0628655),
    ("GRV", "Grove Street", 40.7192583, -74.0421003),
    ("EXP", "Exchange Place", 40.7167341, -74.0324551),
    ("HOB", "Hoboken", 40.7354944, -74.0286157),
    ("NEW", "Newport", 40.7267989, -74.0347553),
    ("WTC", "World Trade Center", 40.7119004, -74.0125270),
    ("CHR", "Christopher St", 40.7329877, -74.0069062),
    ("09S", "9 St", 40.7340749, -73.9996395),
    ("14S", "14 St", 40.7370478, -73.9970695),
    ("23S", "23 St", 40.7428534, -73.9928340),
    ("33S", "33 St", 40.7485384, -73.9887001),
]


def _mta_rows() -> list[tuple[str, str, str, str, str, str, str]]:
    rows = []
    with open(_ASSETS / "mta_stations.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append(
                (
                    record["Stop Name"],
                    "mta",
                    record["GTFS Stop ID"],
                    record["Daytime Routes"].replace(" ", "|"),
                    "",
                    record["GTFS Latitude"],
                    record["GTFS Longitude"],
                )
            )
    return rows


def _path_rows() -> list[tuple[str, str, str, str, str, str, str]]:
    # Every PATH station has the same two direction keys (see
    # PathStation.directions in path_station.dart) - a station near one
    # end of the system may only ever return live data for one of them at
    # fetch time, but that's a live-data fact discovered by calling
    # get_arrivals, not something to filter out of the candidate set here.
    return [
        (name, "path", code, "ToNY|ToNJ", "", str(lat), str(lng))
        for code, name, lat, lng in _PATH_STATIONS
    ]


def _njt_rail_rows() -> list[tuple[str, str, str, str, str, str, str]]:
    rows = []
    with open(_ASSETS / "njt_rail_stations.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append(
                (
                    record["stop_name"],
                    "njt_rail",
                    record["stop_code"],
                    "",
                    "",
                    record["lat"],
                    record["lon"],
                )
            )
    return rows


def _njt_bus_rows() -> list[tuple[str, str, str, str, str, str, str]]:
    rows = []
    with open(_ASSETS / "njt_bus_stops.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append(
                (
                    record["stop_name"],
                    "njt_bus",
                    record["stop_id"],
                    "",
                    record.get("toward", ""),
                    record["lat"],
                    record["lon"],
                )
            )
    return rows


def _lirr_rows() -> list[tuple[str, str, str, str, str, str, str]]:
    rows = []
    with open(_ASSETS / "lirr_stations.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append(
                (
                    record["stop_name"],
                    "lirr",
                    record["stop_code"],
                    "",
                    "",
                    record["lat"],
                    record["lon"],
                )
            )
    return rows


def main() -> None:
    rows = (
        _mta_rows() + _path_rows() + _njt_rail_rows() + _njt_bus_rows() + _lirr_rows()
    )
    with open(_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["name", "agency", "code", "routes", "toward", "lat", "lng"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {_OUT_PATH}")


if __name__ == "__main__":
    main()
