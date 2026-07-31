"""PATH real-time fetching, mirroring lib/path/path_service.dart. Same
unofficial panynj.gov JSON endpoint - see OPEN_QUESTIONS.md for the
sourcing rationale (no official public PATH API exists).
"""

from datetime import datetime, timedelta, timezone

import httpx

from .models import Arrival, ArrivalsResult

_FEED_URL = "https://www.panynj.gov/bin/portauthority/ridepath.json"
_STALE_AFTER = timedelta(minutes=5)


async def get_arrivals(station_code: str, direction: str) -> ArrivalsResult:
    """[direction] is "ToNY" or "ToNJ", matching the feed's own labels
    (see PathStation.directions in the Dart client).
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(_FEED_URL)
    response.raise_for_status()
    body = response.json()

    station_entry = next(
        (
            r
            for r in body.get("results", [])
            if r.get("consideredStation") == station_code
        ),
        None,
    )
    if station_entry is None:
        return ArrivalsResult(arrivals=[], is_live=True)

    destination = next(
        (
            d
            for d in station_entry.get("destinations", [])
            if d.get("label") == direction
        ),
        None,
    )
    if destination is None:
        return ArrivalsResult(arrivals=[], is_live=True)

    arrivals = []
    newest_update = datetime.fromtimestamp(0, tz=timezone.utc)
    now = datetime.now(timezone.utc)

    for message in destination.get("messages", []):
        try:
            seconds_to_arrival = int(message["secondsToArrival"])
            last_updated = datetime.fromisoformat(message["lastUpdated"])
        except (KeyError, ValueError, TypeError):
            continue

        if last_updated.tzinfo is None:
            last_updated = last_updated.replace(tzinfo=timezone.utc)
        newest_update = max(newest_update, last_updated)

        arrivals.append(
            Arrival(
                route_label="PATH",
                arrival_time=now + timedelta(seconds=seconds_to_arrival),
            )
        )

    arrivals.sort(key=lambda a: a.arrival_time)
    is_live = not arrivals or (now - newest_update) < _STALE_AFTER
    return ArrivalsResult(arrivals=arrivals, is_live=is_live)
