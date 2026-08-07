"""Builds app/data/chat_station_index.csv - a compact name -> (agency,
code[, routes]) lookup used only by Chat AI's stateless tier
(app/station_index.py) to resolve a free-text station name from a chat
question into a real code the transit fetchers understand.

Deliberately NOT a copy of any agency's full station CSV (lat/lng, ADA
info, branch lists, etc.) - those already live in the Flutter app's
assets/data/*.csv (source of truth for browsing/search) and, where the
backend also needs to re-fetch arrivals itself (LIRR), in
backend/app/data/*.csv. This script re-derives only the columns Chat AI
actually needs (name, agency, code, and - MTA/PATH only - the routes/
directions a fetch call requires) from those same source files, rather
than hand-maintaining a third copy of station data. Re-run this whenever
an upstream station CSV changes.

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

# Mirrors lib/path/path_station.dart's PathStation.all - keep in sync by
# hand if that list ever changes (see module docstring).
_PATH_STATIONS = [
    ("NWK", "Newark"),
    ("HAR", "Harrison"),
    ("JSQ", "Journal Square"),
    ("GRV", "Grove Street"),
    ("EXP", "Exchange Place"),
    ("HOB", "Hoboken"),
    ("NEW", "Newport"),
    ("WTC", "World Trade Center"),
    ("CHR", "Christopher St"),
    ("09S", "9 St"),
    ("14S", "14 St"),
    ("23S", "23 St"),
    ("33S", "33 St"),
]


def _mta_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    with open(_ASSETS / "mta_stations.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append(
                (
                    record["Stop Name"],
                    "mta",
                    record["GTFS Stop ID"],
                    record["Daytime Routes"].replace(" ", "|"),
                )
            )
    return rows


def _path_rows() -> list[tuple[str, str, str, str]]:
    return [(name, "path", code, "") for code, name in _PATH_STATIONS]


def _njt_rail_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    with open(_ASSETS / "njt_rail_stations.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append((record["stop_name"], "njt_rail", record["stop_code"], ""))
    return rows


def _njt_bus_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    with open(_ASSETS / "njt_bus_stops.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append((record["stop_name"], "njt_bus", record["stop_id"], ""))
    return rows


def _lirr_rows() -> list[tuple[str, str, str, str]]:
    rows = []
    with open(_ASSETS / "lirr_stations.csv", encoding="utf-8") as f:
        for record in csv.DictReader(f):
            rows.append((record["stop_name"], "lirr", record["stop_code"], ""))
    return rows


def main() -> None:
    rows = (
        _mta_rows() + _path_rows() + _njt_rail_rows() + _njt_bus_rows() + _lirr_rows()
    )
    with open(_OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["name", "agency", "code", "routes"])
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {_OUT_PATH}")


if __name__ == "__main__":
    main()
