from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from fpl_mvp.api import FPLClient, FPLNotFound
from fpl_mvp.cache import JsonCache


NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def bootstrap_payload() -> dict:
    return {
        "events": [
            {
                "id": 1,
                "name": "Gameweek 1",
                "deadline_time": "2026-08-21T17:30:00Z",
            }
        ],
        "teams": [{"id": 1, "name": "Arsenal", "short_name": "ARS"}],
        "element_types": [
            {
                "id": 1,
                "singular_name": "Goalkeeper",
                "singular_name_short": "GKP",
                "squad_select": 2,
                "squad_min_play": 1,
                "squad_max_play": 1,
            }
        ],
        "elements": [
            {
                "id": 1,
                "first_name": "Test",
                "second_name": "Keeper",
                "web_name": "Keeper",
                "team": 1,
                "element_type": 1,
                "now_cost": 50,
                "status": "a",
            }
        ],
    }


def test_bootstrap_uses_fresh_cache(tmp_path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=bootstrap_payload(), request=request)

    transport = httpx.MockTransport(handler)
    with FPLClient(
        base_url="https://example.test/api/",
        cache_dir=tmp_path,
        now=lambda: NOW,
        transport=transport,
        sleep=lambda _: None,
    ) as client:
        first = client.get_bootstrap()
        second = client.get_bootstrap()

    assert first.elements[0].web_name == "Keeper"
    assert second.events[0].id == 1
    assert calls == 1
    assert [record.source for record in client.fetch_records] == ["network", "cache"]


def test_stale_cache_is_used_when_network_fails(tmp_path) -> None:
    cache = JsonCache(tmp_path, now=lambda: NOW)
    cache.write("fixtures/", [], fetched_at=NOW - timedelta(hours=2))

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with FPLClient(
        base_url="https://example.test/api/",
        cache_dir=tmp_path,
        cache_ttl_seconds=60,
        retries=2,
        now=lambda: NOW,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    ) as client:
        fixtures = client.get_fixtures()

    assert fixtures == []
    assert client.fetch_records[-1].source == "stale-cache"
    assert client.fetch_records[-1].warning is not None


def test_not_found_is_not_hidden_by_cache(tmp_path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"detail": "Not found."}, request=request)

    with FPLClient(
        base_url="https://example.test/api/",
        cache_dir=tmp_path,
        retries=3,
        now=lambda: NOW,
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    ) as client:
        with pytest.raises(FPLNotFound):
            client.get_picks(3_647_781, 1)

    assert calls == 1

