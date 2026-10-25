"""قرارداد WebSocket hub: کادنس، ``as_of``، نبود داده، timeout و lifecycle.

همهٔ تست‌ها یک کلاینت جعلی و یک ``sleep`` جعلی دارند؛ هیچ اتصال شبکه یا Redis
واقعی لازم نیست.
"""

from __future__ import annotations

import asyncio
import time

import src.gold_desk.ws_hub as ws_hub_module
from src.gold_desk.ws_hub import (
    HOT_INTERVAL_SECONDS,
    SNAPSHOT_INTERVAL_SECONDS,
    GoldWebSocketHub,
    get_hub,
    payload_as_of,
)

AS_OF = "2026-10-25T08:00:00+00:00"


def _snapshot(*, as_of: str | None = AS_OF, source: str = "redis") -> dict:
    snap: dict = {
        "references": {"xau_usd": 2000.0, "usd_irt": 60_000.0, "aed_gap_pct": 1.2},
        "score": {"total": 42, "decision": "GREEN"},
        "coins": {"coin_emami": {"market_price": 10.0, "fair_value": 9.0, "bubble_pct": 11.0}},
        "funds": [],
        "source": source,
    }
    if as_of is not None:
        snap["snapshot_at"] = as_of
    return snap


def _provider(value):
    async def _get():
        return value

    return _get


class FakeWS:
    """کلاینت جعلی که پیام‌ها را جمع می‌کند."""

    def __init__(self) -> None:
        self.messages: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)


class SlowWS(FakeWS):
    """کلاینت جعلی کند: ارسال تا ابد طول می‌کشد."""

    def __init__(self, delay: float = 3600.0) -> None:
        super().__init__()
        self.delay = delay

    async def send_json(self, payload: dict) -> None:
        await asyncio.sleep(self.delay)
        self.messages.append(payload)


class FakeSleep:
    """``sleep`` جعلی: فاصله‌ها را ثبت می‌کند و بعد از ``limit`` حلقه را می‌بندد."""

    def __init__(self, hub: GoldWebSocketHub, limit: int) -> None:
        self.hub = hub
        self.limit = limit
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if len(self.calls) >= self.limit:
            self.hub._stopping = True
        await asyncio.sleep(0)


# ── Cadence ──────────────────────────────────────────────────


async def test_hot_loop_runs_every_ten_seconds() -> None:
    hub = GoldWebSocketHub(hot_provider=_provider(_snapshot()), snapshot_provider=_provider(None))
    ws = FakeWS()
    hub._clients.add(ws)
    clock = FakeSleep(hub, limit=3)
    hub._sleep = clock

    await hub._hot_loop()

    # سه sleep ثبت می‌شود؛ sleep سوم حلقه را می‌بندد، پس دو پیام ارسال شده است.
    assert clock.calls == [HOT_INTERVAL_SECONDS] * 3
    assert clock.calls == [10.0, 10.0, 10.0]
    assert [m["type"] for m in ws.messages] == ["hot", "hot"]
    assert all(m["as_of"] == AS_OF for m in ws.messages)
    assert ws.messages[0]["data"]["status"] == "ok"


async def test_snapshot_loop_runs_every_three_hundred_seconds() -> None:
    snap = _snapshot()
    hub = GoldWebSocketHub(hot_provider=_provider(None), snapshot_provider=_provider(snap))
    ws = FakeWS()
    hub._clients.add(ws)
    clock = FakeSleep(hub, limit=2)
    hub._sleep = clock

    await hub._snapshot_loop()

    assert clock.calls == [SNAPSHOT_INTERVAL_SECONDS] * 2
    assert clock.calls == [300.0, 300.0]
    assert 30.0 not in clock.calls
    assert [m["type"] for m in ws.messages] == ["snapshot"]
    assert ws.messages[0]["as_of"] == AS_OF
    assert ws.messages[0]["data"] == snap


async def test_hot_payload_comes_from_hotpath_snapshot_not_local_cache() -> None:
    local = _snapshot(as_of="2026-01-01T00:00:00+00:00", source="local")
    fresh = _snapshot(source="hotpath")
    hub = GoldWebSocketHub(hot_provider=_provider(fresh), snapshot_provider=_provider(None))
    hub.cache_snapshot(local)
    ws = FakeWS()
    hub._clients.add(ws)

    await hub.broadcast(await hub._hot_message())

    assert len(ws.messages) == 1
    message = ws.messages[0]
    assert message["as_of"] == AS_OF
    assert "score" in message["data"]
    assert message["data"]["timestamp"] == AS_OF


# ── as_of / no data ──────────────────────────────────────────


def test_payload_as_of_accepts_iso_and_epoch() -> None:
    assert payload_as_of({"as_of": AS_OF}) == AS_OF
    assert payload_as_of({"data": {"snapshot_at": AS_OF}}) == AS_OF
    assert payload_as_of({"data": {"ts": 1_700_000_000.0}}) == "2023-11-14T22:13:20+00:00"
    assert payload_as_of({"data": {}}) is None
    assert payload_as_of(None) is None


async def test_no_message_without_data() -> None:
    hub = GoldWebSocketHub(hot_provider=_provider(None), snapshot_provider=_provider(None))
    ws = FakeWS()
    hub._clients.add(ws)
    clock = FakeSleep(hub, limit=2)
    hub._sleep = clock

    await hub._hot_loop()
    clock.calls.clear()
    await hub._snapshot_loop()

    assert ws.messages == []

    # snapshot بدون snapshot_at هم دادهٔ زمان‌دار نیست.
    hub2 = GoldWebSocketHub(
        hot_provider=_provider({"score": {"total": 1}}),
        snapshot_provider=_provider(_snapshot(as_of=None)),
    )
    assert await hub2._hot_message() is None
    assert await hub2._snapshot_message() is None


async def test_empty_broadcast_payload_is_never_sent() -> None:
    hub = GoldWebSocketHub()
    ws = FakeWS()
    hub._clients.add(ws)

    await hub.broadcast({})
    await hub.broadcast({"type": "snapshot", "data": {}})

    assert ws.messages == []


# ── Timeout / slow clients ───────────────────────────────────


async def test_slow_client_times_out_and_is_dropped() -> None:
    hub = GoldWebSocketHub(send_timeout=0.05)
    fast, slow = FakeWS(), SlowWS()
    hub._clients.update({fast, slow})

    started = time.monotonic()
    await hub.broadcast({"type": "snapshot", "data": {"snapshot_at": AS_OF}})
    elapsed = time.monotonic() - started

    assert len(fast.messages) == 1
    assert slow not in hub._clients
    assert fast in hub._clients
    assert elapsed < 1.0


async def test_one_slow_client_does_not_block_the_others() -> None:
    hub = GoldWebSocketHub(send_timeout=5.0)
    clients = [SlowWS(delay=0.15) for _ in range(2)]
    fast = FakeWS()
    hub._clients.update([*clients, fast])

    started = time.monotonic()
    await hub.broadcast({"type": "snapshot", "data": {"snapshot_at": AS_OF}})
    elapsed = time.monotonic() - started

    assert len(fast.messages) == 1
    # سریال ≈ ۰.۳۰s می‌شد؛ هم‌زمان ≈ ۰.۱۵s.
    assert elapsed < 0.28


async def test_register_sends_cached_snapshot_with_timeout() -> None:
    hub = GoldWebSocketHub(snapshot_provider=_provider(_snapshot()))
    ws = FakeWS()

    await hub.register(ws)

    assert ws.messages[0]["type"] == "snapshot"
    assert ws.messages[0]["as_of"] == AS_OF
    assert hub.client_count() == 1
    await hub.unregister(ws)
    assert hub.client_count() == 0


# ── Cross-process snapshot ───────────────────────────────────


async def test_snapshot_prefers_redis_over_local_memory() -> None:
    hub = GoldWebSocketHub(snapshot_provider=_provider(_snapshot(source="redis")))
    hub.cache_snapshot(_snapshot(as_of="2026-01-01T00:00:00+00:00", source="local"))
    ws = FakeWS()
    hub._clients.add(ws)

    message = await hub._snapshot_message()
    assert message is not None
    await hub.broadcast(message)

    assert ws.messages[0]["data"]["source"] == "redis"
    assert ws.messages[0]["as_of"] == AS_OF


async def test_snapshot_falls_back_to_local_memory_when_redis_is_empty() -> None:
    hub = GoldWebSocketHub(snapshot_provider=_provider(None))
    hub.cache_snapshot(_snapshot(source="local"))

    message = await hub._snapshot_message()

    assert message is not None
    assert message["data"]["source"] == "local"


# ── Lifecycle ────────────────────────────────────────────────


def test_get_hub_does_not_create_a_task_outside_an_event_loop(monkeypatch) -> None:
    monkeypatch.setattr(ws_hub_module, "_hub", None)

    hub = get_hub()

    assert hub.is_running() is False


async def test_ensure_started_starts_loops_only_once_and_stop_cancels_them() -> None:
    hub = GoldWebSocketHub(
        hot_interval=3600.0,
        snapshot_interval=3600.0,
        hot_provider=_provider(_snapshot()),
        snapshot_provider=_provider(_snapshot()),
    )

    await hub.ensure_started()
    tasks = list(hub._tasks)
    await hub.ensure_started()

    assert hub.is_running() is True
    assert hub._tasks == tasks
    assert len(tasks) == 2

    await hub.stop()

    assert hub.is_running() is False
    assert all(task.cancelled() or task.done() for task in tasks)


async def test_stop_is_safe_when_never_started() -> None:
    hub = GoldWebSocketHub()

    await hub.stop()

    assert hub.is_running() is False


async def test_hot_loop_survives_provider_errors() -> None:
    async def _boom():
        raise RuntimeError("redis down")

    hub = GoldWebSocketHub(hot_provider=_boom, snapshot_provider=_provider(None))
    ws = FakeWS()
    hub._clients.add(ws)
    clock = FakeSleep(hub, limit=2)
    hub._sleep = clock

    await hub._hot_loop()

    assert ws.messages == []
    assert clock.calls == [HOT_INTERVAL_SECONDS] * 2
