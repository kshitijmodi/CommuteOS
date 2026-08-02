"""One-off script: joins NJT's static GTFS rail feed (stops.txt + stop_times.txt
+ trips.txt + routes.txt) into a clean bundled asset for the Flutter app -
station code, name, lat/lng, and which lines serve it. Not part of the
running app; re-run manually if NJT's GTFS feed ever needs refreshing (see
OPEN_QUESTIONS.md on the same tradeoff already made for MTA's station CSV).

Usage: python build_njt_rail_stations.py <path-to-extracted-gtfs-dir> <output-csv-path>
"""

import csv
import sys
from collections import defaultdict


def main() -> None:
    gtfs_dir, output_path = sys.argv[1], sys.argv[2]

    with open(f"{gtfs_dir}/routes.txt", encoding="utf-8-sig") as f:
        routes_by_id = {r["route_id"]: r for r in csv.DictReader(f)}

    with open(f"{gtfs_dir}/trips.txt", encoding="utf-8-sig") as f:
        route_id_by_trip = {t["trip_id"]: t["route_id"] for t in csv.DictReader(f)}

    lines_by_stop_id: dict[str, set[str]] = defaultdict(set)
    with open(f"{gtfs_dir}/stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            route_id = route_id_by_trip.get(row["trip_id"])
            if route_id is None:
                continue
            route = routes_by_id.get(route_id)
            if route is None:
                continue
            lines_by_stop_id[row["stop_id"]].add(route["route_short_name"])

    with open(f"{gtfs_dir}/stops.txt", encoding="utf-8-sig") as f:
        stops = list(csv.DictReader(f))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        # Explicit \n line terminator: csv.writer's default is \r\n, which
        # doesn't match the Flutter side's CsvToListConverter(eol: '\n')
        # (same convention as the existing MTA station CSV) - with \r\n,
        # the header's last column parses as "lines\r", silently breaking
        # every header.indexOf() lookup for that column.
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["stop_code", "stop_name", "lat", "lon", "lines"])
        for stop in stops:
            code = stop["stop_code"].strip()
            if not code:
                continue
            lines = sorted(lines_by_stop_id.get(stop["stop_id"], set()))
            writer.writerow(
                [code, stop["stop_name"], stop["stop_lat"], stop["stop_lon"], "|".join(lines)]
            )

    print(f"Wrote {len(stops)} stations to {output_path}")


if __name__ == "__main__":
    main()
