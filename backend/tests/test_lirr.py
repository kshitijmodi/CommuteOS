from datetime import datetime, timezone

import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from app.transit import lirr


@pytest.fixture(autouse=True)
def _reset_caches():
    """Both bundled lookups are cached at module scope - reset between
    tests so state doesn't leak."""
    lirr._branch_by_trip_id = None
    lirr._stop_id_by_stop_code = None
    yield
    lirr._branch_by_trip_id = None
    lirr._stop_id_by_stop_code = None


def _install_mock_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


def _build_feed(
    entities: list[tuple[str, list[tuple[str, int]]]],
    canceled_trip_ids: set[str] | None = None,
) -> bytes:
    """entities: list of (trip_id, [(stop_id, epoch_seconds), ...])."""
    canceled_trip_ids = canceled_trip_ids or set()
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    for i, (trip_id, stops) in enumerate(entities):
        e = feed.entity.add()
        e.id = str(i)
        e.trip_update.trip.trip_id = trip_id
        if trip_id in canceled_trip_ids:
            e.trip_update.trip.schedule_relationship = (
                gtfs_realtime_pb2.TripDescriptor.CANCELED
            )
        for stop_id, epoch_seconds in stops:
            stu = e.trip_update.stop_time_update.add()
            stu.stop_id = stop_id
            if epoch_seconds > 0:
                stu.arrival.time = epoch_seconds
    return feed.SerializeToString()


def _mock_handler(feed_bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        assert "lirr" in str(request.url)
        return httpx.Response(200, content=feed_bytes)

    return handler


@pytest.mark.asyncio
async def test_get_arrivals_translates_stop_code_to_numeric_stop_id(monkeypatch):
    """Regression test for the real gotcha: the real-time feed matches
    against LIRR's numeric stop_id ("102" for Jamaica), not the 3-letter
    stop_code ("JAM") this app uses as the public station identifier
    everywhere else - get_arrivals must translate before matching."""
    lirr._stop_id_by_stop_code = {"JAM": "102"}
    lirr._branch_by_trip_id = {"T1": "Babylon Branch"}

    feed_bytes = _build_feed([("T1", [("102", 1900000000)])])
    _install_mock_transport(monkeypatch, _mock_handler(feed_bytes))

    result = await lirr.get_arrivals("JAM")

    assert result.is_live is True
    assert len(result.arrivals) == 1
    assert result.arrivals[0].route_label == "Babylon Branch"
    assert result.arrivals[0].arrival_time == datetime.fromtimestamp(
        1900000000, tz=timezone.utc
    )


@pytest.mark.asyncio
async def test_get_arrivals_filters_by_requested_station(monkeypatch):
    lirr._stop_id_by_stop_code = {"JAM": "102"}
    lirr._branch_by_trip_id = {"T1": "Babylon Branch"}

    feed_bytes = _build_feed([("T1", [("102", 1900000000), ("999", 1900000100)])])
    _install_mock_transport(monkeypatch, _mock_handler(feed_bytes))

    result = await lirr.get_arrivals("JAM")

    assert len(result.arrivals) == 1


@pytest.mark.asyncio
async def test_get_arrivals_falls_back_to_lirr_label_for_unknown_trip(monkeypatch):
    lirr._stop_id_by_stop_code = {"JAM": "102"}
    lirr._branch_by_trip_id = {}

    feed_bytes = _build_feed([("unknown-trip", [("102", 1900000000)])])
    _install_mock_transport(monkeypatch, _mock_handler(feed_bytes))

    result = await lirr.get_arrivals("JAM")

    assert result.arrivals[0].route_label == "LIRR"


@pytest.mark.asyncio
async def test_get_arrivals_skips_canceled_trips(monkeypatch):
    """Regression test: a CANCELED trip reports stops with no timing data
    at all (verified against a real feed response) - must be skipped
    rather than surfaced as a phantom arrival with no real time."""
    lirr._stop_id_by_stop_code = {"JAM": "102"}
    lirr._branch_by_trip_id = {"T1": "Babylon Branch", "T2": "Montauk Branch"}

    feed_bytes = _build_feed(
        [("T1", [("102", 0)]), ("T2", [("102", 1900000000)])],
        canceled_trip_ids={"T1"},
    )
    _install_mock_transport(monkeypatch, _mock_handler(feed_bytes))

    result = await lirr.get_arrivals("JAM")

    assert len(result.arrivals) == 1
    assert result.arrivals[0].route_label == "Montauk Branch"


@pytest.mark.asyncio
async def test_get_arrivals_falls_back_to_raw_code_when_not_in_lookup(monkeypatch):
    """If a station code isn't in the bundled lookup (shouldn't happen for
    a real station, but shouldn't crash either), get_arrivals falls back
    to matching the raw code directly rather than raising."""
    lirr._stop_id_by_stop_code = {}
    lirr._branch_by_trip_id = {"T1": "Babylon Branch"}

    feed_bytes = _build_feed([("T1", [("UNKNOWNCODE", 1900000000)])])
    _install_mock_transport(monkeypatch, _mock_handler(feed_bytes))

    result = await lirr.get_arrivals("UNKNOWNCODE")

    assert len(result.arrivals) == 1


@pytest.mark.asyncio
async def test_get_arrivals_raises_on_malformed_feed(monkeypatch):
    lirr._stop_id_by_stop_code = {}
    lirr._branch_by_trip_id = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not a valid protobuf!!")

    _install_mock_transport(monkeypatch, handler)

    with pytest.raises(lirr.LirrFeedException):
        await lirr.get_arrivals("JAM")


@pytest.mark.asyncio
async def test_get_arrivals_raises_on_http_failure(monkeypatch):
    lirr._stop_id_by_stop_code = {}
    lirr._branch_by_trip_id = {}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(502)

    _install_mock_transport(monkeypatch, handler)

    with pytest.raises(lirr.LirrFeedException):
        await lirr.get_arrivals("JAM")
