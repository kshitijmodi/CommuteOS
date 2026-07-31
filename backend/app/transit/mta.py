"""MTA GTFS-realtime fetching, mirroring lib/mta/mta_feed.dart and
lib/mta/mta_service.dart. Public, unauthenticated feeds - see that Dart
module's docstring for the same "no API key needed" verification this
project already did once for the mobile app.
"""

import httpx
from google.transit import gtfs_realtime_pb2

from .models import Arrival, ArrivalsResult

_FEED_BASE = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds"

# Mirrors MtaFeed in mta_feed.dart - not derivable from static GTFS, MTA
# doesn't publish this mapping, so it's hardcoded on both sides.
_FEED_PATHS = {
    "numbered": "nyct%2Fgtfs",
    "ace": "nyct%2Fgtfs-ace",
    "bdfm": "nyct%2Fgtfs-bdfm",
    "g": "nyct%2Fgtfs-g",
    "jz": "nyct%2Fgtfs-jz",
    "nqrw": "nyct%2Fgtfs-nqrw",
    "l": "nyct%2Fgtfs-l",
    "sir": "nyct%2Fgtfs-si",
}

_ROUTE_TO_FEED = {
    "1": "numbered", "2": "numbered", "3": "numbered", "4": "numbered",
    "5": "numbered", "6": "numbered", "7": "numbered", "S": "numbered", "GS": "numbered",
    "A": "ace", "C": "ace", "E": "ace", "H": "ace", "SR": "ace",
    "B": "bdfm", "D": "bdfm", "F": "bdfm", "M": "bdfm", "FS": "bdfm", "SF": "bdfm",
    "G": "g",
    "J": "jz", "Z": "jz",
    "N": "nqrw", "Q": "nqrw", "R": "nqrw", "W": "nqrw",
    "L": "l",
    "SI": "sir", "SIR": "sir",
}


def feed_for_route(route_id: str) -> str | None:
    return _ROUTE_TO_FEED.get(route_id)


async def get_arrivals(stop_id: str, route_id: str) -> ArrivalsResult:
    """Fetches the feed for [route_id] and returns arrivals at [stop_id].

    MTA's feed has no separate staleness signal beyond fetch success/failure
    (unlike PATH) - a successful fetch is always treated as live, matching
    MtaService.getArrivals in the Dart client.
    """
    feed_key = feed_for_route(route_id)
    if feed_key is None:
        return ArrivalsResult(arrivals=[], is_live=False)

    url = f"{_FEED_BASE}/{_FEED_PATHS[feed_key]}"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url)
    response.raise_for_status()

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(response.content)

    arrivals = []
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip_update = entity.trip_update
        if trip_update.trip.route_id != route_id:
            continue

        for stop_time_update in trip_update.stop_time_update:
            if stop_time_update.stop_id != stop_id:
                continue
            if not stop_time_update.HasField("arrival"):
                continue
            epoch_seconds = stop_time_update.arrival.time
            if epoch_seconds <= 0:
                continue

            from datetime import datetime, timezone

            arrivals.append(
                Arrival(
                    route_label=route_id,
                    arrival_time=datetime.fromtimestamp(
                        epoch_seconds, tz=timezone.utc
                    ),
                )
            )

    arrivals.sort(key=lambda a: a.arrival_time)
    return ArrivalsResult(arrivals=arrivals, is_live=True)
