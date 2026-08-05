import httpx
import pytest
from google.transit import gtfs_realtime_pb2

from app.transit import njt_bus


@pytest.fixture(autouse=True)
def _reset_caches():
    """Both the auth token and the trip->route lookup are cached at module
    scope - reset between tests so state doesn't leak."""
    njt_bus._cached_token = None
    njt_bus._cached_token_at = 0.0
    njt_bus._route_by_trip_id = None
    yield
    njt_bus._cached_token = None
    njt_bus._cached_token_at = 0.0
    njt_bus._route_by_trip_id = None


def _install_mock_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


def _build_feed(entities: list[tuple[str, str, list[tuple[str, int]]]]) -> bytes:
    """entities: list of (trip_id, route_id, [(stop_id, epoch_seconds), ...])."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    for i, (trip_id, route_id, stops) in enumerate(entities):
        e = feed.entity.add()
        e.id = str(i)
        e.trip_update.trip.trip_id = trip_id
        e.trip_update.trip.route_id = route_id
        for stop_id, epoch_seconds in stops:
            stu = e.trip_update.stop_time_update.add()
            stu.stop_id = stop_id
            stu.arrival.time = epoch_seconds
    return feed.SerializeToString()


def _mock_handler(auth_response, feed_bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/authenticateUser"):
            return httpx.Response(200, json=auth_response)
        if request.url.path.endswith("/getTripUpdates"):
            return httpx.Response(200, content=feed_bytes)
        raise AssertionError(f"Unexpected request to {request.url}")

    return handler


@pytest.mark.asyncio
async def test_get_arrivals_joins_route_via_bundled_trip_lookup(monkeypatch, tmp_path):
    monkeypatch.setattr(njt_bus.settings, "njt_username", "user")
    monkeypatch.setattr(njt_bus.settings, "njt_password", "pass")
    # NJT's real feed reports an empty route_id - the bundled trip lookup
    # (not the feed itself) is what supplies the real route label.
    njt_bus._route_by_trip_id = {"500": "409"}

    feed_bytes = _build_feed([("500", "", [("12345", 1900000000)])])
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, feed_bytes),
    )

    result = await njt_bus.get_arrivals(["12345"])

    assert result.is_live is True
    assert len(result.arrivals) == 1
    assert result.arrivals[0].route_label == "409"


@pytest.mark.asyncio
async def test_get_arrivals_filters_by_requested_stop_id(monkeypatch):
    monkeypatch.setattr(njt_bus.settings, "njt_username", "user")
    monkeypatch.setattr(njt_bus.settings, "njt_password", "pass")
    njt_bus._route_by_trip_id = {"500": "409"}

    feed_bytes = _build_feed(
        [("500", "", [("12345", 1900000000), ("99999", 1900000100)])]
    )
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, feed_bytes),
    )

    result = await njt_bus.get_arrivals(["12345"])

    assert len(result.arrivals) == 1


@pytest.mark.asyncio
async def test_get_arrivals_merges_multiple_stop_ids_in_one_feed_fetch(monkeypatch):
    """Regression test for the real "Journal Square has 26 separate bay
    stop_ids with no single combined arrivals view" bug - a caller can now
    pass every bay's stop_id and get one merged, soonest-first list back
    from a single feed fetch, rather than being forced to pick one bay.
    """
    monkeypatch.setattr(njt_bus.settings, "njt_username", "user")
    monkeypatch.setattr(njt_bus.settings, "njt_password", "pass")
    njt_bus._route_by_trip_id = {"1": "1", "2": "2", "3": "10"}

    feed_bytes = _build_feed(
        [
            ("1", "", [("16792", 1900000200)]),  # trip "1" -> route "1", bay 16792
            ("2", "", [("16802", 1900000100)]),  # trip "2" -> route "2", bay 16802 - soonest
            ("3", "", [("16943", 1900000300)]),  # trip "3" -> route "10", bay 16943
            ("4", "", [("99999", 1900000050)]),  # a bay NOT requested - must be excluded
        ]
    )
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, feed_bytes),
    )

    result = await njt_bus.get_arrivals(["16792", "16802", "16943"])

    assert [a.route_label for a in result.arrivals] == ["2", "1", "10"]


@pytest.mark.asyncio
async def test_get_arrivals_falls_back_to_bus_label_for_unknown_trip(monkeypatch):
    monkeypatch.setattr(njt_bus.settings, "njt_username", "user")
    monkeypatch.setattr(njt_bus.settings, "njt_password", "pass")
    njt_bus._route_by_trip_id = {}

    feed_bytes = _build_feed([("unknown-trip", "", [("12345", 1900000000)])])
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, feed_bytes),
    )

    result = await njt_bus.get_arrivals(["12345"])

    assert result.arrivals[0].route_label == "Bus"


@pytest.mark.asyncio
async def test_get_arrivals_skips_updates_with_no_arrival_field(monkeypatch):
    monkeypatch.setattr(njt_bus.settings, "njt_username", "user")
    monkeypatch.setattr(njt_bus.settings, "njt_password", "pass")
    njt_bus._route_by_trip_id = {"500": "409"}

    feed = gtfs_realtime_pb2.FeedMessage()
    feed.header.gtfs_realtime_version = "2.0"
    e = feed.entity.add()
    e.id = "0"
    e.trip_update.trip.trip_id = "500"
    stu = e.trip_update.stop_time_update.add()
    stu.stop_id = "12345"
    # Deliberately no .arrival field set.

    _install_mock_transport(
        monkeypatch,
        _mock_handler(
            {"Authenticated": "True", "UserToken": "abc123"}, feed.SerializeToString()
        ),
    )

    result = await njt_bus.get_arrivals(["12345"])

    assert result.arrivals == []


@pytest.mark.asyncio
async def test_get_token_raises_when_credentials_missing(monkeypatch):
    monkeypatch.setattr(njt_bus.settings, "njt_username", None)
    monkeypatch.setattr(njt_bus.settings, "njt_password", None)

    with pytest.raises(njt_bus.NjtBusFeedException):
        await njt_bus._get_token()


@pytest.mark.asyncio
async def test_get_arrivals_raises_on_malformed_feed(monkeypatch):
    monkeypatch.setattr(njt_bus.settings, "njt_username", "user")
    monkeypatch.setattr(njt_bus.settings, "njt_password", "pass")
    njt_bus._route_by_trip_id = {}

    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, b"not a valid protobuf!!"),
    )

    with pytest.raises(njt_bus.NjtBusFeedException):
        await njt_bus.get_arrivals(["12345"])
