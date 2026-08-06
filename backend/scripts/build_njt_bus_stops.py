"""One-off script: joins NJT's static GTFS bus feed (stops.txt + stop_times.txt
+ trips.txt + routes.txt) into a clean bundled asset for the Flutter app -
stop id, name, lat/lng, which routes serve it, and (see [toward] below) a
best-effort "toward <terminus>" hint. Filtered to a NYC-metro "core"
bounding box (Hudson/Essex/Union/Bergen counties, roughly - where
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
from collections import Counter, defaultdict

# Roughly Hudson/Essex/Union/northern Middlesex/southern Bergen counties -
# covers Newark, Jersey City, Hoboken, Elizabeth, up toward the NY state
# line, matching where MTA/PATH/NJT rail service already concentrates.
_LAT_MIN, _LAT_MAX = 40.60, 40.90
_LON_MIN, _LON_MAX = -74.30, -74.05


def _toward_by_stop_id(
    stop_times_path: str,
    route_id_by_trip: dict[str, str],
    direction_id_by_trip: dict[str, str],
    long_name_by_route: dict[str, str],
) -> dict[str, str]:
    """Best-effort "toward <terminus>" hint per stop_id, needed because a
    stop_id alone carries no direction info (NJT's real-time API returns
    whichever buses are due there, no direction split to query by - see
    njt_bus.py) - two stop_ids sharing an exact name can be genuinely
    different physical stops on opposite sides of an intersection, serving
    opposite directions (a real bug found via phone testing: "1st Ave at
    Aldene Rd"'s two stop_ids are ~113m apart, one toward Newark, one away
    from it). Without a label, the station picker showed two identical-
    looking rows with no way to tell them apart.

    NJT's route_long_name follows the standard GTFS convention of
    "<direction_id=0 terminus> - <direction_id=1 terminus>" (e.g. route
    59's "Plainfield - Newark"). For each stop_id, find its single most
    common (route_id, direction_id) pair across every trip serving it, then
    pick the matching half of that route's long_name. This is a hint, not
    exact routing data - a trip's specific headsign can vary within one
    direction (e.g. some direction-0 trips end at Plainfield, others at
    Westfield) - picking the route's overall terminus instead of a
    specific trip's headsign avoids ever showing a headsign that's
    technically wrong for a given bus while still being directionally
    correct. Empty string when there's no long_name to split, the route
    isn't found, or a stop is genuinely mixed/ambiguous (no dominant pair).
    """
    combo_counts: dict[str, Counter[tuple[str, str]]] = defaultdict(Counter)
    with open(stop_times_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            trip_id = row["trip_id"]
            route_id = route_id_by_trip.get(trip_id)
            direction_id = direction_id_by_trip.get(trip_id)
            if route_id is None or direction_id not in ("0", "1"):
                continue
            combo_counts[row["stop_id"]][(route_id, direction_id)] += 1

    toward_by_stop_id: dict[str, str] = {}
    for stop_id, counts in combo_counts.items():
        (route_id, direction_id), _ = counts.most_common(1)[0]
        long_name = long_name_by_route.get(route_id, "")
        parts = [p.strip() for p in long_name.split(" - ")]
        if len(parts) != 2:
            continue
        toward_by_stop_id[stop_id] = parts[int(direction_id)]

    return toward_by_stop_id


def main() -> None:
    gtfs_dir, output_path = sys.argv[1], sys.argv[2]

    with open(f"{gtfs_dir}/routes.txt", encoding="utf-8-sig") as f:
        routes_by_id = {r["route_id"]: r for r in csv.DictReader(f)}

    with open(f"{gtfs_dir}/trips.txt", encoding="utf-8-sig") as f:
        trips = list(csv.DictReader(f))
        route_id_by_trip = {t["trip_id"]: t["route_id"] for t in trips}
        direction_id_by_trip = {t["trip_id"]: t["direction_id"] for t in trips}

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

    long_name_by_route = {rid: r["route_long_name"] for rid, r in routes_by_id.items()}
    toward_by_stop_id = _toward_by_stop_id(
        f"{gtfs_dir}/stop_times.txt", route_id_by_trip, direction_id_by_trip, long_name_by_route
    )

    with open(f"{gtfs_dir}/stops.txt", encoding="utf-8-sig") as f:
        stops = list(csv.DictReader(f))

    written = 0
    skipped_light_rail = 0
    skipped_out_of_area = 0

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["stop_id", "stop_name", "lat", "lon", "routes", "toward"])
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
            toward = toward_by_stop_id.get(stop["stop_id"], "")
            writer.writerow([stop["stop_id"], name, lat, lon, "|".join(routes), toward])
            written += 1

    print(
        f"Wrote {written} stops "
        f"(skipped {skipped_light_rail} light rail, {skipped_out_of_area} out-of-area) "
        f"to {output_path}"
    )


if __name__ == "__main__":
    main()
