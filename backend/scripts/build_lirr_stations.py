"""One-off script: joins the MTA's static LIRR GTFS feed (stops.txt +
stop_times.txt + trips.txt + routes.txt) into two clean bundled assets for
the Flutter app: the station list (stop_id, code, name, branches), and a
trip_id -> (branch, headsign) lookup.

Unlike NJT rail (one call returns everything at a station, no branch
concept) or MTA subway (a station has a small fixed line-group set), LIRR
stations aren't tied to one branch - a hub like Jamaica is served by most
of the system's 13 branches, and trains terminate at one of several
distinct terminals (Penn Station, Grand Central, Atlantic Terminal,
Hunterspoint Avenue). The real-time GTFS-RT feed gives a trip_id + route_id
per update but no headsign/destination text - confirmed by inspecting a
real feed response, trip_id there matches a static trips.txt trip_id
exactly (e.g. "GO201_26_809" -> route "6"/Long Beach Branch, headsign
"Grand Central") - so the real destination needs this join, same pattern
as NJT bus's trip_id->route lookup (app/data/njt_bus_trip_routes.csv). At
~2,100 trips (vs. NJT bus's ~46k), this is small enough to bundle directly
in the Flutter app and join client-side rather than needing a backend
proxy - LIRR's real-time feed is public/unauthenticated (confirmed live at
api-endpoint.mta.info), so there's no credential reason to proxy it either.

Real gotcha: the real-time feed's stop_time_update.stop_id is the
NUMERIC GTFS stop_id (e.g. "102" for Jamaica), NOT the 3-letter stop_code
("JAM") used everywhere else in this app for LIRR station identity -
confirmed by inspecting a real feed response and cross-referencing
stops.txt. The bundled station CSV includes BOTH: stop_id (what the
real-time API match needs) and stop_code (what the app displays/uses as
the station's public id, matching every other agency's convention here).

Not part of the running app; re-run manually if MTA's LIRR GTFS feed ever
needs refreshing (see OPEN_QUESTIONS.md on the same tradeoff already made
for MTA subway's and NJT's station CSVs).

Usage: python build_lirr_stations.py <path-to-extracted-gtfs-dir> <stations-output-csv> <trip-routes-output-csv>
"""

import csv
import sys
from collections import defaultdict


def main() -> None:
    gtfs_dir, stations_output_path, trip_routes_output_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(f"{gtfs_dir}/routes.txt", encoding="utf-8-sig") as f:
        routes_by_id = {r["route_id"]: r for r in csv.DictReader(f)}

    with open(f"{gtfs_dir}/trips.txt", encoding="utf-8-sig") as f:
        trips = list(csv.DictReader(f))
    route_id_by_trip = {t["trip_id"]: t["route_id"] for t in trips}

    branches_by_stop_id: dict[str, set[str]] = defaultdict(set)
    with open(f"{gtfs_dir}/stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            route_id = route_id_by_trip.get(row["trip_id"])
            if route_id is None:
                continue
            route = routes_by_id.get(route_id)
            if route is None:
                continue
            branches_by_stop_id[row["stop_id"]].add(route["route_long_name"])

    with open(f"{gtfs_dir}/stops.txt", encoding="utf-8-sig") as f:
        stops = list(csv.DictReader(f))

    # Explicit \n line terminator throughout: csv.writer's default is
    # \r\n, which doesn't match the Flutter side's
    # CsvToListConverter(eol: '\n') (same convention as every other bundled
    # CSV in this app) - with \r\n, the header's last column parses with a
    # trailing "\r", silently breaking every header.indexOf() lookup.
    with open(stations_output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["stop_id", "stop_code", "stop_name", "lat", "lon", "branches"])
        for stop in stops:
            code = stop["stop_code"].strip()
            if not code:
                continue
            branches = sorted(branches_by_stop_id.get(stop["stop_id"], set()))
            writer.writerow(
                [
                    stop["stop_id"],
                    code,
                    stop["stop_name"],
                    stop["stop_lat"],
                    stop["stop_lon"],
                    "|".join(branches),
                ]
            )
    print(f"Wrote {len(stops)} stations to {stations_output_path}")

    with open(trip_routes_output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["trip_id", "branch", "headsign"])
        for trip in trips:
            route = routes_by_id.get(trip["route_id"])
            branch = route["route_long_name"] if route else ""
            writer.writerow([trip["trip_id"], branch, trip["trip_headsign"]])
    print(f"Wrote {len(trips)} trip routes to {trip_routes_output_path}")


if __name__ == "__main__":
    main()
