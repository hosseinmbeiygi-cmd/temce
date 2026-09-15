import json

import pytest

from services.realtime_service import ConnectionManager, RealtimeService


@pytest.mark.asyncio
async def test_connection_manager_tracks_subscriptions() -> None:
    manager = ConnectionManager()
    await manager.connect("c1", ["GOLD", "USD"])
    await manager.subscribe("c2", ["GOLD"])

    assert manager.total_connections == 2
    assert await manager.get_subscribers("GOLD") == {"c1", "c2"}

    await manager.unsubscribe("c1", ["GOLD"])
    assert await manager.get_subscribers("GOLD") == {"c2"}
    await manager.disconnect("c2")
    assert await manager.get_subscribers("GOLD") == set()


@pytest.mark.asyncio
async def test_broadcast_price_caches_and_pushes_to_subscribers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCache:
        def __init__(self) -> None:
            self.saved: list[tuple[str, dict, int]] = []

        async def set(self, key: str, value: dict, ttl: int) -> None:
            self.saved.append((key, value, ttl))

    cache = FakeCache()
    monkeypatch.setattr("services.realtime_service.get_cache", lambda: cache)
    service = RealtimeService()
    sent: list[str] = []
    await service.register_client("c1", sent.append, ["GOLD"])

    await service.broadcast_price("GOLD", {"price": 100, "timestamp": "2026-08-30T08:00:00Z"})

    # Pushed live to the subscriber (flat payload: action+symbol+data fields)
    assert sent and json.loads(sent[0])["action"] == "price"
    assert json.loads(sent[0])["symbol"] == "GOLD"
    assert json.loads(sent[0])["price"] == 100
    # Cached with the service's TTL for late joiners
    assert cache.saved[0][0] == "realtime:prices:GOLD"
    assert cache.saved[0][2] == 30


@pytest.mark.asyncio
async def test_pong_replies_to_ping() -> None:
    service = RealtimeService()
    sent: list[str] = []
    await service.register_client("c1", sent.append, [])

    await service.handle_message("c1", json.dumps({"action": "ping"}))

    payload = json.loads(sent[0])
    assert payload["action"] == "pong"
    assert "ts" in payload
