from datetime import datetime, timezone

import httpx
import pytest

from app.transit.path import get_arrivals


def _install_mock_transport(monkeypatch, response_json: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=response_json)

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient

    def patched(*args, **kwargs):
        kwargs.setdefault("transport", transport)
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", patched)


@pytest.mark.asyncio
async def test_get_arrivals_carries_the_real_headsign_per_arrival(monkeypatch):
    # Real bug fixed 2026-08-08: this feed genuinely reports a distinct
    # "headSign" per message (confirmed against a live response) but it
    # was discarded entirely before this - every arrival looked identical
    # regardless of its real destination, which is what let chat_ai.py
    # hallucinate an answer to "what about the other direction."
    now_iso = datetime.now(timezone.utc).isoformat()
    _install_mock_transport(
        monkeypatch,
        {
            "results": [
                {
                    "consideredStation": "JSQ",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "target": "33S",
                                    "secondsToArrival": "120",
                                    "arrivalTimeMessage": "2 min",
                                    "lineColor": "FF9900",
                                    "headSign": "33rd Street",
                                    "lastUpdated": now_iso,
                                },
                                {
                                    "target": "WTC",
                                    "secondsToArrival": "600",
                                    "arrivalTimeMessage": "10 min",
                                    "lineColor": "D93A30",
                                    "headSign": "World Trade Center",
                                    "lastUpdated": now_iso,
                                },
                            ],
                        }
                    ],
                }
            ]
        },
    )

    result = await get_arrivals("JSQ", "ToNY")

    assert len(result.arrivals) == 2
    assert result.arrivals[0].headsign == "33rd Street"
    assert result.arrivals[1].headsign == "World Trade Center"


@pytest.mark.asyncio
async def test_get_arrivals_falls_back_to_target_when_headsign_is_missing(monkeypatch):
    now_iso = datetime.now(timezone.utc).isoformat()
    _install_mock_transport(
        monkeypatch,
        {
            "results": [
                {
                    "consideredStation": "JSQ",
                    "destinations": [
                        {
                            "label": "ToNY",
                            "messages": [
                                {
                                    "target": "33S",
                                    "secondsToArrival": "120",
                                    "lastUpdated": now_iso,
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )

    result = await get_arrivals("JSQ", "ToNY")

    assert result.arrivals[0].headsign == "33S"
