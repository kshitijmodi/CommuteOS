"""NJ Transit BUS real-time fetching, via NJT's GTFSG2 API (getTripUpdates)
- NOT the BUSDV2 API tested earlier, which only exposes a static route
list (getBusRoutes), no real-time arrivals. GTFSG2's data is standard
GTFS-realtime protobuf, the same format MTA already uses (mta.py) - the
`gtfs_realtime_bindings`/`gtfs-realtime-bindings` dependency is shared.

Real difference from MTA: NJT bus's feed is ONE single feed covering every
route (not split per line-group like MTA's), and each trip_update's
`trip.route_id` field is reported EMPTY by NJT - the only way to know
which bus line an update belongs to is joining its `trip_id` against the
static GTFS's trips.txt (bundled here as app/data/njt_bus_trip_routes.csv,
see backend/scripts/build_njt_bus_trip_routes.py for how it's built/why
it's bundled rather than fetched live).
"""

import csv
import time
from datetime import datetime, timezone
from importlib import resources

import httpx
from google.transit import gtfs_realtime_pb2

from ..core.config import settings
from .models import Arrival, ArrivalsResult

_TOKEN_URL = "https://pcsdata.njtransit.com/api/GTFSG2/authenticateUser"
_TRIP_UPDATES_URL = "https://pcsdata.njtransit.com/api/GTFSG2/getTripUpdates"

# Same 24h-token/rate-limited-minting reasoning as njt_rail.py.
_TOKEN_LIFETIME_SECONDS = 23 * 60 * 60

_cached_token: str | None = None
_cached_token_at: float = 0.0

_route_by_trip_id: dict[str, str] | None = None


class NjtBusFeedException(Exception):
    pass


def _load_route_by_trip_id() -> dict[str, str]:
    global _route_by_trip_id
    if _route_by_trip_id is not None:
        return _route_by_trip_id

    with resources.files("app.data").joinpath("njt_bus_trip_routes.csv").open(
        "r", encoding="utf-8"
    ) as f:
        _route_by_trip_id = {row["trip_id"]: row["route_short_name"] for row in csv.DictReader(f)}
    return _route_by_trip_id


async def _get_token() -> str:
    global _cached_token, _cached_token_at

    if _cached_token and (time.monotonic() - _cached_token_at) < _TOKEN_LIFETIME_SECONDS:
        return _cached_token

    if not settings.njt_username or not settings.njt_password:
        raise NjtBusFeedException("NJT_USERNAME/NJT_PASSWORD not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _TOKEN_URL,
            data={"username": settings.njt_username, "password": settings.njt_password},
        )
    response.raise_for_status()
    body = response.json()

    if body.get("Authenticated") != "True" or not body.get("UserToken"):
        raise NjtBusFeedException(f"NJT bus authentication failed: {body}")

    _cached_token = body["UserToken"]
    _cached_token_at = time.monotonic()
    return _cached_token


async def get_arrivals(stop_ids: list[str]) -> ArrivalsResult:
    """Fetches arrivals for one or more stop_ids in a single feed fetch and
    merges them, sorted soonest-first.

    Large terminals (e.g. Journal Square) are split across many separate
    bay-level stop_ids in NJT's own static GTFS - there's no single stop_id
    that represents "every bus at this terminal." Since this feed already
    covers every route in one fetch (see the module docstring), accepting
    multiple stop_ids costs nothing extra over a single one - it's the
    same feed, just matched against a larger stop_id set - so the caller
    (a combined-terminal NjtBusStop on the Flutter side) can present one
    merged arrivals view instead of forcing a pick among near-identical bays.
    """
    token = await _get_token()
    route_by_trip_id = _load_route_by_trip_id()
    wanted_stop_ids = set(stop_ids)

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.post(_TRIP_UPDATES_URL, data={"token": token})
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    try:
        feed.ParseFromString(response.content)
    except Exception as e:
        raise NjtBusFeedException(f"Failed to parse NJT bus GTFS-RT feed: {e}") from e

    arrivals = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip_update = entity.trip_update
        route_label = route_by_trip_id.get(trip_update.trip.trip_id, "Bus")

        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id not in wanted_stop_ids:
                continue
            if not stop_time_update.HasField("arrival"):
                continue
            epoch_seconds = stop_time_update.arrival.time
            if epoch_seconds <= 0:
                continue

            arrivals.append(
                Arrival(
                    route_label=route_label,
                    arrival_time=datetime.fromtimestamp(epoch_seconds, tz=timezone.utc),
                )
            )

    arrivals.sort(key=lambda a: a.arrival_time)
    # No separate staleness signal in this feed beyond fetch success/failure
    # - same reasoning as mta.py/njt_rail.py.
    return ArrivalsResult(arrivals=arrivals, is_live=True)
