"""Proxies real-time transit fetches that need a secret credential the
mobile app must never hold directly. NJT rail/bus both require a real
username/password (see app/transit/njt_rail.py, njt_bus.py) - unlike
MTA/PATH, which are public/unauthenticated and so the Flutter app calls
them directly. No auth required here: browsing arrivals has never
required an account anywhere else in the app (see OPEN_QUESTIONS.md on
that pattern), and this holds no per-user data - it's a pure pass-through
to NJT's own public transit data.
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from ..transit import njt_bus, njt_rail
from ..transit.models import ArrivalsResult

router = APIRouter(prefix="/transit", tags=["transit"])


class ArrivalOut(BaseModel):
    route_label: str
    arrival_time: str


class ArrivalsResultOut(BaseModel):
    arrivals: list[ArrivalOut]
    is_live: bool


def _to_response(result: ArrivalsResult) -> ArrivalsResultOut:
    return ArrivalsResultOut(
        arrivals=[
            ArrivalOut(route_label=a.route_label, arrival_time=a.arrival_time.isoformat())
            for a in result.arrivals
        ],
        is_live=result.is_live,
    )


@router.get("/njt-rail/{station_code}", response_model=ArrivalsResultOut)
async def get_njt_rail_arrivals(station_code: str):
    try:
        result = await njt_rail.get_arrivals(station_code)
    except njt_rail.NjtFeedException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return _to_response(result)


@router.get("/njt-bus/{stop_id}", response_model=ArrivalsResultOut)
async def get_njt_bus_arrivals(
    stop_id: str,
    extra_stop_ids: str = Query(
        default="",
        description=(
            "Comma-separated additional stop_ids to merge into one response - "
            "for a combined-terminal view spanning several bay-level stop_ids "
            "that don't otherwise share one arrivals feed entry point (e.g. "
            "Journal Square's ~26 separate NJT bus bays). {stop_id} is always "
            "included; this just adds more."
        ),
    ),
):
    stop_ids = [stop_id, *[s for s in extra_stop_ids.split(",") if s]]
    try:
        result = await njt_bus.get_arrivals(stop_ids)
    except njt_bus.NjtBusFeedException as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return _to_response(result)
