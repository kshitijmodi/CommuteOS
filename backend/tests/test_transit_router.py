from datetime import datetime, timedelta, timezone

from app.transit.models import Arrival, ArrivalsResult


def test_njt_rail_endpoint_requires_no_auth(client, monkeypatch):
    async def fake_get_arrivals(station_code):
        return ArrivalsResult(arrivals=[], is_live=True)

    monkeypatch.setattr("app.routers.transit.njt_rail.get_arrivals", fake_get_arrivals)

    response = client.get("/transit/njt-rail/NP")

    assert response.status_code == 200


def test_njt_rail_endpoint_returns_arrivals(client, monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_get_arrivals(station_code):
        assert station_code == "NP"
        return ArrivalsResult(
            arrivals=[Arrival(route_label="NEC", arrival_time=now + timedelta(minutes=5))],
            is_live=True,
        )

    monkeypatch.setattr("app.routers.transit.njt_rail.get_arrivals", fake_get_arrivals)

    response = client.get("/transit/njt-rail/NP")

    assert response.status_code == 200
    body = response.json()
    assert body["is_live"] is True
    assert len(body["arrivals"]) == 1
    assert body["arrivals"][0]["route_label"] == "NEC"


def test_njt_rail_endpoint_returns_502_on_feed_failure(client, monkeypatch):
    from app.transit.njt_rail import NjtFeedException

    async def fake_get_arrivals(station_code):
        raise NjtFeedException("boom")

    monkeypatch.setattr("app.routers.transit.njt_rail.get_arrivals", fake_get_arrivals)

    response = client.get("/transit/njt-rail/NP")

    assert response.status_code == 502


def test_njt_bus_endpoint_returns_arrivals(client, monkeypatch):
    now = datetime.now(timezone.utc)

    async def fake_get_arrivals(stop_ids):
        assert stop_ids == ["1941"]
        return ArrivalsResult(
            arrivals=[Arrival(route_label="163", arrival_time=now + timedelta(minutes=8))],
            is_live=True,
        )

    monkeypatch.setattr("app.routers.transit.njt_bus.get_arrivals", fake_get_arrivals)

    response = client.get("/transit/njt-bus/1941")

    assert response.status_code == 200
    body = response.json()
    assert body["arrivals"][0]["route_label"] == "163"


def test_njt_bus_endpoint_merges_extra_stop_ids(client, monkeypatch):
    """A combined-terminal request (e.g. Journal Square's many bay stop_ids)
    passes the primary stop_id plus extra_stop_ids - regression test that
    the router assembles the full list correctly and forwards it as-is."""
    now = datetime.now(timezone.utc)

    async def fake_get_arrivals(stop_ids):
        assert stop_ids == ["16792", "16802", "16943"]
        return ArrivalsResult(arrivals=[], is_live=True)

    monkeypatch.setattr("app.routers.transit.njt_bus.get_arrivals", fake_get_arrivals)

    response = client.get("/transit/njt-bus/16792?extra_stop_ids=16802,16943")

    assert response.status_code == 200


def test_njt_bus_endpoint_returns_502_on_feed_failure(client, monkeypatch):
    from app.transit.njt_bus import NjtBusFeedException

    async def fake_get_arrivals(stop_ids):
        raise NjtBusFeedException("boom")

    monkeypatch.setattr("app.routers.transit.njt_bus.get_arrivals", fake_get_arrivals)

    response = client.get("/transit/njt-bus/1941")

    assert response.status_code == 502
