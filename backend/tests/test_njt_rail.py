import httpx
import pytest

from app.transit import njt_rail


@pytest.fixture(autouse=True)
def _reset_token_cache():
    """The module caches its auth token at module scope - reset between
    tests so one test's cached token can't leak into another's mocked
    transport."""
    njt_rail._cached_token = None
    njt_rail._cached_token_at = 0.0
    yield
    njt_rail._cached_token = None
    njt_rail._cached_token_at = 0.0


def _install_mock_transport(monkeypatch, handler):
    """Patches httpx.AsyncClient so every client the module under test
    constructs (it never passes its own `transport`) routes through this
    handler instead of a real network call."""
    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


def _mock_handler(auth_response, schedule_response):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getToken"):
            return httpx.Response(200, json=auth_response)
        if request.url.path.endswith("/getTrainSchedule19Rec"):
            return httpx.Response(200, json=schedule_response)
        raise AssertionError(f"Unexpected request to {request.url}")

    return handler


@pytest.mark.asyncio
async def test_get_arrivals_computes_delay_adjusted_time(monkeypatch):
    monkeypatch.setattr(njt_rail.settings, "njt_username", "user")
    monkeypatch.setattr(njt_rail.settings, "njt_password", "pass")

    schedule = {
        "STATION_2CHAR": "NP",
        "ITEMS": [
            {
                "SCHED_DEP_DATE": "01-Aug-2026 12:25:00 PM",
                "DESTINATION": "New York",
                "LINE": "Northeast Corrdr",
                "LINECODE": "NE",
                "STATUS": "in 6 Min",
                "SEC_LATE": "300",
            }
        ],
    }
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, schedule),
    )

    result = await njt_rail.get_arrivals("NP")

    assert result.is_live is True
    assert len(result.arrivals) == 1
    arrival = result.arrivals[0]
    assert arrival.route_label == "NE"
    # SCHED_DEP_DATE (12:25:00 PM) + SEC_LATE (300s = 5min) = 12:30:00 PM
    assert arrival.arrival_time.hour == 12
    assert arrival.arrival_time.minute == 30


@pytest.mark.asyncio
async def test_get_arrivals_handles_negative_sec_late_early_train(monkeypatch):
    monkeypatch.setattr(njt_rail.settings, "njt_username", "user")
    monkeypatch.setattr(njt_rail.settings, "njt_password", "pass")

    schedule = {
        "ITEMS": [
            {
                "SCHED_DEP_DATE": "01-Aug-2026 12:25:00 PM",
                "DESTINATION": "New York",
                "LINECODE": "NE",
                "STATUS": "in 5 Min",
                "SEC_LATE": "-60",
            }
        ]
    }
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, schedule),
    )

    result = await njt_rail.get_arrivals("NP")

    assert result.arrivals[0].arrival_time.minute == 24


@pytest.mark.asyncio
async def test_get_arrivals_skips_items_with_unparseable_date(monkeypatch):
    monkeypatch.setattr(njt_rail.settings, "njt_username", "user")
    monkeypatch.setattr(njt_rail.settings, "njt_password", "pass")

    schedule = {
        "ITEMS": [
            {"SCHED_DEP_DATE": "garbage", "SEC_LATE": "0", "LINECODE": "NE"},
            {
                "SCHED_DEP_DATE": "01-Aug-2026 12:25:00 PM",
                "SEC_LATE": "0",
                "LINECODE": "NE",
            },
        ]
    }
    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "True", "UserToken": "abc123"}, schedule),
    )

    result = await njt_rail.get_arrivals("NP")

    assert len(result.arrivals) == 1


@pytest.mark.asyncio
async def test_get_token_raises_when_credentials_missing(monkeypatch):
    monkeypatch.setattr(njt_rail.settings, "njt_username", None)
    monkeypatch.setattr(njt_rail.settings, "njt_password", None)

    with pytest.raises(njt_rail.NjtFeedException):
        await njt_rail._get_token()


@pytest.mark.asyncio
async def test_get_token_raises_on_failed_auth(monkeypatch):
    monkeypatch.setattr(njt_rail.settings, "njt_username", "user")
    monkeypatch.setattr(njt_rail.settings, "njt_password", "wrong")

    _install_mock_transport(
        monkeypatch,
        _mock_handler({"Authenticated": "False", "UserToken": ""}, {}),
    )

    with pytest.raises(njt_rail.NjtFeedException):
        await njt_rail._get_token()


@pytest.mark.asyncio
async def test_token_is_cached_across_calls(monkeypatch):
    monkeypatch.setattr(njt_rail.settings, "njt_username", "user")
    monkeypatch.setattr(njt_rail.settings, "njt_password", "pass")

    call_count = {"auth": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/getToken"):
            call_count["auth"] += 1
            return httpx.Response(200, json={"Authenticated": "True", "UserToken": "abc123"})
        return httpx.Response(200, json={"ITEMS": []})

    _install_mock_transport(monkeypatch, handler)

    await njt_rail.get_arrivals("NP")
    await njt_rail.get_arrivals("NP")

    assert call_count["auth"] == 1
