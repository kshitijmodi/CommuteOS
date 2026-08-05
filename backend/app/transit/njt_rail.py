"""NJ Transit RAIL real-time fetching, mirroring the pattern in path.py/mta.py.

Verified against the real API (developer account approved 2026-08-01) -
notably NOT the legacy SOAP/XML endpoint the original njt.py scaffold's
docstring worried about. `raildata.njtransit.com/api/TrainData/...` is a
modern JSON API, same shape as the BUSDATA API. (NJ Transit's own docs
show the host as `raildata.njt.gov` - that domain does not resolve;
`raildata.njtransit.com` is the real one, confirmed by testing both.)

Real gotchas found while integrating, documented here rather than left as
a surprise later:
- SCHED_DEP_DATE is the *scheduled* time; SEC_LATE (seconds, can be
  negative for an early train) must be added to get the real predicted
  time - NJT does not give you a single "predicted arrival" field like
  MTA/PATH do.
- STATUS is a mixed bag: a countdown string ("in 6 Min"), a state word
  ("DELAYED", "ON TIME", "ALL ABOARD" - inconsistently cased, sometimes
  "All Aboard"), or a blank " " for trains far enough out that no status
  is assigned yet. Not used for scoring (SEC_LATE is authoritative and
  numeric) - shown to the user as-is/best-effort only.
- DESTINATION occasionally contains a raw unescaped HTML entity (e.g.
  "Trenton &#9992;" - a plane emoji indicating an airport connection) -
  must be unescaped or it displays literally.
"""

import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

from ..core.config import settings
from .models import Arrival, ArrivalsResult

_TOKEN_URL = "https://raildata.njtransit.com/api/TrainData/getToken"
_SCHEDULE_URL = "https://raildata.njtransit.com/api/TrainData/getTrainSchedule19Rec"

# Tokens are valid 24h per NJT's docs; refresh a bit early to avoid a
# request failing right at the boundary. Token minting is itself
# rate-limited (per NJT's docs) - caching is not an optimization here,
# it's required to stay within that limit.
_TOKEN_LIFETIME_SECONDS = 23 * 60 * 60

# NJT's timestamps have no offset and are always Eastern local time (the
# whole service is NYC-metro only) - this is the one place that fact needs
# to be made explicit, converting to a real UTC instant.
_EASTERN = ZoneInfo("America/New_York")

_cached_token: str | None = None
_cached_token_at: float = 0.0


class NjtFeedException(Exception):
    pass


async def _get_token() -> str:
    global _cached_token, _cached_token_at

    if _cached_token and (time.monotonic() - _cached_token_at) < _TOKEN_LIFETIME_SECONDS:
        return _cached_token

    if not settings.njt_username or not settings.njt_password:
        raise NjtFeedException("NJT_USERNAME/NJT_PASSWORD not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _TOKEN_URL,
            data={"username": settings.njt_username, "password": settings.njt_password},
        )
    response.raise_for_status()
    body = response.json()

    if body.get("Authenticated") != "True" or not body.get("UserToken"):
        raise NjtFeedException(f"NJT authentication failed: {body}")

    _cached_token = body["UserToken"]
    _cached_token_at = time.monotonic()
    return _cached_token


def _parse_predicted_arrival(item: dict) -> datetime | None:
    try:
        # e.g. "01-Aug-2026 10:20:00 AM"
        scheduled = datetime.strptime(item["SCHED_DEP_DATE"], "%d-%b-%Y %I:%M:%S %p")
        sec_late = int(item.get("SEC_LATE") or 0)
    except (KeyError, ValueError, TypeError):
        return None
    # scheduled is a naive Eastern-local wall-clock value (NJT gives no
    # offset). Attach the real IANA zone first, THEN add the delay and
    # convert to UTC - this correctly handles the EDT/EST DST transition
    # (a fixed-hours-offset shortcut would be wrong on either side of it).
    # Previously this attached tzinfo=timezone.utc directly, which mislabels
    # the Eastern wall-clock value as if it were already UTC without
    # actually converting it - every arrival was off by the real UTC
    # offset (4-5 hours), which is why arrival times looked wrong/like
    # "now" once clients started comparing against a real UTC "now".
    eastern_time = scheduled.replace(tzinfo=_EASTERN) + timedelta(seconds=sec_late)
    return eastern_time.astimezone(timezone.utc)


async def get_arrivals(station_code: str) -> ArrivalsResult:
    token = await _get_token()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            _SCHEDULE_URL,
            data={"token": token, "station": station_code, "line": ""},
        )
    response.raise_for_status()
    body = response.json()

    items = body.get("ITEMS") or []
    arrivals = []
    for item in items:
        arrival_time = _parse_predicted_arrival(item)
        if arrival_time is None:
            continue

        line = (item.get("LINECODE") or item.get("LINE") or "NJT").strip()

        arrivals.append(
            Arrival(
                route_label=line or "NJT",
                arrival_time=arrival_time,
            )
        )

    arrivals.sort(key=lambda a: a.arrival_time)
    # NJT's real-time feed has no separate staleness signal like PATH's
    # lastUpdated - if the request succeeded at all, treat it as live,
    # same reasoning as mta.py.
    return ArrivalsResult(arrivals=arrivals, is_live=True)
