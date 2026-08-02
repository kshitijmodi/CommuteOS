"""One-off script: joins NJT's static GTFS bus feed (stops.txt + stop_times.txt
+ trips.txt + routes.txt) into a clean bundled asset for the Flutter app -
stop id, name, lat/lng, and which routes serve it. Filtered to a NYC-metro
"core" bounding box (Hudson/Essex/Union/Bergen counties, roughly - where
MTA/PATH/NJT rail already concentrate) rather than all ~17k statewide
stops, per the PRD's NYC-metro scope decision. Also excludes NJT's light
rail stations (Newark Light Rail, HBLR), which share this same stops.txt
file but are a different transit mode, not "bus."

Not part of the running app; re-run manually if NJT's GTFS feed ever needs
refreshing (same tradeoff as MTA's and NJT rail's bundled station CSVs).

Usage: python build_njt_bus_stops.py <path-to-extracted-gtfs-dir> <output-csv-path>
"""

import csv
import sys
from collections import defaultdict

# Roughly Hudson/Essex/Union/northern Middlesex/southern Bergen counties -
# covers Newark, Jersey City, Hoboken, Elizabeth, up toward the NY state
# line, matching where MTA/PATH/NJT rail service already concentrates.
_LAT_MIN, _LAT_MAX = 40.60, 40.90
_LON_MIN, _LON_MAX = -74.30, -74.05


def main() -> None:
    gtfs_dir, output_path = sys.argv[1], sys.argv[2]

    with open(f"{gtfs_dir}/routes.txt", encoding="utf-8-sig") as f:
        routes_by_id = {r["route_id"]: r for r in csv.DictReader(f)}

    with open(f"{gtfs_dir}/trips.txt", encoding="utf-8-sig") as f:
        route_id_by_trip = {t["trip_id"]: t["route_id"] for t in csv.DictReader(f)}

    routes_by_stop_id: dict[str, set[str]] = defaultdict(set)
    with open(f"{gtfs_dir}/stop_times.txt", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            route_id = route_id_by_trip.get(row["trip_id"])
            if route_id is None:
                continue
            route = routes_by_id.get(route_id)
            if route is None:
                continue
            routes_by_stop_id[row["stop_id"]].add(route["route_short_name"])

    with open(f"{gtfs_dir}/stops.txt", encoding="utf-8-sig") as f:
        stops = list(csv.DictReader(f))

    written = 0
    skipped_light_rail = 0
    skipped_out_of_area = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["stop_id", "stop_name", "lat", "lon", "routes"])
        for stop in stops:
            name = stop["stop_name"].strip()
            if "LIGHT RAIL" in name.upper():
                skipped_light_rail += 1
                continue

            try:
                lat, lon = float(stop["stop_lat"]), float(stop["stop_lon"])
            except (KeyError, ValueError):
                skipped_out_of_area += 1
                continue

            if not (_LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX):
                skipped_out_of_area += 1
                continue

            routes = sorted(routes_by_stop_id.get(stop["stop_id"], set()))
            writer.writerow([stop["stop_id"], name, lat, lon, "|".join(routes)])
            written += 1

    print(
        f"Wrote {written} stops "
        f"(skipped {skipped_light_rail} light rail, {skipped_out_of_area} out-of-area) "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
