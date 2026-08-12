"""Keeps NJT bus's real-time trip_id -> route_short_name mapping fresh
(see transit/njt_bus.py's module docstring for the real bug this fixes -
NJT reshuffles real bus trip_ids completely within days, so the bundled
CSV baseline goes 100% stale within about a week and a half).

Can be run manually (`python -m app.jobs.refresh_njt_bus_routes`) or, in
production, is triggered DAILY via POST /internal/run-njt-bus-refresh-job
(see routers/internal.py, .github/workflows/njt-bus-routes-refresh.yml) -
same reasoning as the other internal jobs: Render's free tier has no
built-in cron and the web service spins down when idle, so nothing
hosted there can reliably self-schedule.
"""

from ..transit.njt_bus import refresh_route_by_trip_id


async def run() -> int:
    """Returns the number of trip_id rows loaded, so the endpoint/manual
    run can report it - a suspiciously low or zero count would be a real
    signal something's wrong with NJT's feed or credentials, not just a
    "did it run" boolean.
    """
    return await refresh_route_by_trip_id()


def main() -> None:
    import asyncio

    row_count = asyncio.run(run())
    print(f"Refreshed NJT bus trip_id -> route mapping: {row_count} rows.")


if __name__ == "__main__":
    main()
