"""LIRR (Long Island Rail Road, MTA-operated) real-time fetching, via the
same GTFS-realtime infrastructure MTA subway already uses
(api-endpoint.mta.info) - confirmed live, public, and unauthenticated (no
API key needed), unlike NJT rail/bus which need real credentials. This
mirrors mta.py's direct-fetch pattern, not njt_rail.py/njt_bus.py's
credential-proxy pattern - there's no secret here to keep off the client,
but the backend still needs its own fetch for candidate-scoring
(recommendation_builder.py) and the scheduled notification job, the same
reason mta.py exists alongside the Flutter app's own direct-fetching
MtaService.

Real difference from MTA subway: LIRR stations aren't tied to one line/
line-group - a hub like Jamaica is served by most of the system's 13
branches, and trains terminate at one of several distinct terminals (Penn
Station, Grand Central, Atlantic Terminal, Hunterspoint Avenue). The
real-time feed gives a trip_id + route_id + per-stop arrival time per
update, but no destination/headsign text - confirmed by inspecting a real
feed response, a trip_id there matches a trip_id in LIRR's static GTFS
trips.txt exactly, so the real branch name comes from a bundled
trip_id -> branch lookup (app/data/lirr_trip_routes.csv, see
backend/scripts/build_lirr_stations.py - the same file bundled into the
Flutter app too, built once from the same static GTFS).

Real gotcha: the real-time feed's stop_time_update.stop_id is the
NUMERIC GTFS stop_id (e.g. "102" for Jamaica), NOT the 3-letter stop_code
("JAM") this app uses everywhere else as LIRR's public station id
(favorites, home/office inference, etc. - matching every other agency's
convention here) - confirmed by inspecting a real feed response and
cross-referencing stops.txt. get_arrivals takes the public stop_code and
translates it via a bundled stop_code -> stop_id lookup
(app/data/lirr_stations.csv, the same file bundled into the Flutter app).
"""

import csv
from datetime import datetime, timezone
from importlib import resources

import httpx
from google.transit import gtfs_realtime_pb2

from .models import Arrival, ArrivalsResult

_FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/lirr%2Fgtfs-lirr"

_CANCELED = 3  # TripDescriptor.ScheduleRelationship.CANCELED (see gtfs-realtime.proto)

_branch_by_trip_id: dict[str, str] | None = None
_stop_id_by_stop_code: dict[str, str] | None = None


class LirrFeedException(Exception):
    pass


def _load_branch_by_trip_id() -> dict[str, str]:
    global _branch_by_trip_id
    if _branch_by_trip_id is not None:
        return _branch_by_trip_id

    with resources.files("app.data").joinpath("lirr_trip_routes.csv").open(
        "r", encoding="utf-8"
    ) as f:
        _branch_by_trip_id = {row["trip_id"]: row["branch"] for row in csv.DictReader(f)}
    return _branch_by_trip_id


def _load_stop_id_by_stop_code() -> dict[str, str]:
    global _stop_id_by_stop_code
    if _stop_id_by_stop_code is not None:
        return _stop_id_by_stop_code

    with resources.files("app.data").joinpath("lirr_stations.csv").open(
        "r", encoding="utf-8"
    ) as f:
        _stop_id_by_stop_code = {row["stop_code"]: row["stop_id"] for row in csv.DictReader(f)}
    return _stop_id_by_stop_code


async def get_arrivals(station_code: str) -> ArrivalsResult:
    branch_by_trip_id = _load_branch_by_trip_id()
    stop_id_by_stop_code = _load_stop_id_by_stop_code()
    stop_id = stop_id_by_stop_code.get(station_code, station_code)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(_FEED_URL)
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise LirrFeedException(f"Failed to reach LIRR feed: {e}") from e

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(response.content)
    except Exception as e:
        raise LirrFeedException(f"Failed to parse LIRR feed: {e}") from e

    arrivals = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip_update = entity.trip_update
        # CANCELED trips report stops with no timing data at all (verified
        # against a real feed response) - skip rather than surface a
        # cancellation as a phantom arrival with no time.
        if trip_update.trip.schedule_relationship == _CANCELED:
            continue
        branch = branch_by_trip_id.get(trip_update.trip.trip_id, "LIRR")

        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id != stop_id:
                continue
            if not stop_time_update.HasField("arrival"):
                continue
            epoch_seconds = stop_time_update.arrival.time
            if epoch_seconds <= 0:
                continue

            arrivals.append(
                Arrival(
                    route_label=branch,
                    arrival_time=datetime.fromtimestamp(epoch_seconds, tz=timezone.utc),
                )
            )

    arrivals.sort(key=lambda a: a.arrival_time)
    # No separate staleness signal in this feed beyond fetch success/failure
    # - same reasoning as mta.py/njt_rail.py/njt_bus.py.
    return ArrivalsResult(arrivals=arrivals, is_live=True)
