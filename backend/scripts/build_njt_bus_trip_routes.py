"""One-off script: extracts a trip_id -> route_id (route_short_name) mapping
from NJT's static bus GTFS feed (trips.txt joined with routes.txt). NJT's
real-time GTFS-RT feed (getTripUpdates) reports a trip_id per update but
leaves route_id empty, so this backend-side lookup is required to know
which bus line a given real-time update belongs to.

Bundled as a static asset rather than fetched live at request time, since
the static GTFS feed itself needs its own auth+download (45MB zip) - see
OPEN_QUESTIONS.md for the tradeoff (this mapping can go stale between
manual refreshes if NJT reshuffles trip_ids, same tradeoff already made
for the bundled MTA/NJT-rail/NJT-bus station lists).

Usage: python build_njt_bus_trip_routes.py <path-to-extracted-gtfs-dir> <output-csv-path>
"""

import csv
import sys


def main() -> None:
    gtfs_dir, output_path = sys.argv[1], sys.argv[2]

    with open(f"{gtfs_dir}/routes.txt", encoding="utf-8-sig") as f:
        route_name_by_id = {r["route_id"]: r["route_short_name"] for r in csv.DictReader(f)}

    with open(f"{gtfs_dir}/trips.txt", encoding="utf-8-sig") as f:
        trips = list(csv.DictReader(f))

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["trip_id", "route_short_name"])
        written = 0
        for trip in trips:
            route_name = route_name_by_id.get(trip["route_id"])
            if not route_name:
                continue
            writer.writerow([trip["trip_id"], route_name])
            written += 1

    print(f"Wrote {written} trip->route mappings to {output_path}")


if __name__ == "__main__":
    main()
