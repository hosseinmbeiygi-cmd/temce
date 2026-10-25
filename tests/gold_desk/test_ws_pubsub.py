"""قرارداد Redis Pub/Sub برای رویدادهای WebSocket طلا (بدون Redis واقعی).

سمت job (``live_signals``/``gold_desk_jobs``) رویداد را publish می‌کند و سمت API
(``GoldWebSocketHub``) آن را در همان process به کلاینت‌ها می‌رساند. همهٔ تست‌ها
با کلاینت/کش جعلی کار می‌کنند؛ هیچ اتصال شبکه‌ای لازم نیست.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time

import core.cache as cache_module
import src.gold_desk.ws_hub as ws_hub_module
from src.gold_desk.live_signals import REDIS_KEY_PREV_SNAP, detect_and_broadcast
from src.gold_desk.ws_hub import (
    GOLD_WS_CHANNEL,
    SUBSCRIBER_BACKOFF_SECONDS,
    GoldWebSocketHub,
    publish_ws_event,
)

AS_OF = "2026-10-25T08:00:00+00:00"
TS = 1_700_000_000.0
TS_ISO = "2023-11-14T22:13:20+00:00"


# ── Fakes ────────────────────────────────────────────────────


class RecordingWS:
    """کلاینت جعلی که پیام‌ها را جمع می‌کند."""

    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.received = asyncio.Event()

    async def send_json(self, payload: dict) -> None:
        self.messages.append(payload)
        self.received.set()


class FakePubSub:
    def __init__(self, messages: list[dict] | None = None, *, block: bool = True) -> None:
        self._messages = list(messages or [])
        self._block = block
        self._stop = asyncio.Event()
        self.channels: list[str] = []
        self.closed = False

    async def subscribe(self, channel: str) -> None:
        self.channels.append(channel)

    async def listen(self):
        for message in self._messages:
            yield message
        if self._block:
            await self._stop.wait()

    async def aclose(self) -> None:
        self.closed = True
        self._stop.set()


class FakeRedisClient:
    def __init__(self, *, pubsub=None, publish_error: BaseException | None = None) -> None:
        self._pubsub = pubsub
        self._publish_error = publish_error
        self.published: list[tuple[str, str]] = []

    async def publish(self, channel: str, message: str) -> int:
        if self._publish_error is not None:
            raise self._publish_error
        self.published.append((channel, message))
        return 1

    def pubsub(self):
        if isinstance(self._pubsub, BaseException):
            raise self._pubsub
        if self._pubsub is None:
            raise RuntimeError("no pubsub configured")
        return self._pubsub


class FakeCache:
    def __init__(self, client) -> None:
        self.client = client


class JobCache:
    """کش جعلیِ کافی برای مسیر ``detect_and_broadcast``."""

    def __init__(self, client, prev_payload: str | None = None) -> None:
        self.client = client
        self.data: dict[str, object] = {}
        if prev_payload is not None:
            self.data[REDIS_KEY_PREV_SNAP] = prev_payload

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value, ttl: int | None = None) -> None:
        self.data[key] = value


def _install_cache(monkeypatch, cache) -> None:
    monkeypatch.setattr(cache_module, "get_cache", lambda: cache)


def _message(payload) -> dict:
    raw = payload if isinstance(payload, str) else json.dumps(payload)
    return {"type": "message", "channel": GOLD_WS_CHANNEL, "data": raw}


def _provider(value):
    async def _get():
        return value

    return _get


def _snapshot(*, as_of: str = AS_OF) -> dict:
    return {
        "references": {"xau_usd": 2000.0, "usd_irt": 60_000.0, "aed_gap_pct": 1.2},
        "score": {"total": 42, "decision": "GREEN"},
        "coins": {"coin_emami": {"market_price": 10.0, "fair_value": 9.0, "bubble_pct": 11.0}},
        "funds": [],
        "snapshot_at": as_of,
    }


# ── Publish (job process) ────────────────────────────────────


async def test_publish_from_job_uses_channel_and_keeps_payload_keys(monkeypatch) -> None:
    client = FakeRedisClient()
    _install_cache(monkeypatch, FakeCache(client))

    ok = await publish_ws_event({"type": "signal", "data": {"symbol": "X", "ts": TS}})

    assert ok is True
    channel, raw = client.published[0]
    assert channel == GOLD_WS_CHANNEL
    payload = json.loads(raw)
    assert payload["type"] == "signal"
    assert payload["data"] == {"symbol": "X", "ts": TS}
    # as_of از data.ts ساخته می‌شود و هیچ کلید دیگری تغییر نمی‌کند.
    assert payload["as_of"] == TS_ISO


async def test_publish_is_skipped_without_redis(monkeypatch) -> None:
    _install_cache(monkeypatch, FakeCache(None))

    ok = await publish_ws_event({"type": "signal", "data": {"ts": TS}})

    assert ok is False


async def test_publish_without_as_of_is_not_sent(monkeypatch) -> None:
    client = FakeRedisClient()
    _install_cache(monkeypatch, FakeCache(client))

    ok = await publish_ws_event({"type": "signal", "data": {}})

    assert ok is False
    assert client.published == []


async def test_publish_redis_error_does_not_raise(monkeypatch) -> None:
    client = FakeRedisClient(publish_error=ConnectionError("redis down"))
    _install_cache(monkeypatch, FakeCache(client))

    ok = await publish_ws_event({"type": "signal", "data": {"ts": TS}})

    assert ok is False


async def test_signal_job_publishes_instead_of_local_broadcast(monkeypatch) -> None:
    prev = json.dumps(
        {
            "ts": time.time(),
            "snapshot": {
                "coins": {
                    "coin_emami": {
                        "symbol": "IR_COIN_EMAMI",
                        "display_name": "سکه",
                        "market_price": 100.0,
                    }
                },
                "score": {"total": 50},
                "references": {},
            },
        }
    )
    client = FakeRedisClient()
    _install_cache(monkeypatch, JobCache(client, prev))
    current = {
        "coins": {
            "coin_emami": {
                "symbol": "IR_COIN_EMAMI",
                "display_name": "سکه",
                "market_price": 110.0,
            }
        },
        "score": {"total": 50},
        "references": {},
    }

    signals = await detect_and_broadcast(current)

    assert len(signals) == 1
    assert client.published, "job must publish the signal for the API process"
    channel, raw = client.published[0]
    assert channel == GOLD_WS_CHANNEL
    payload = json.loads(raw)
    assert payload["type"] == "signal"
    assert payload["data"]["symbol"] == "IR_COIN_EMAMI"
    assert payload["as_of"]


async def test_signal_job_survives_publish_error(monkeypatch) -> None:
    prev = json.dumps(
        {
            "ts": time.time(),
            "snapshot": {
                "coins": {"coin_emami": {"symbol": "IR_COIN_EMAMI", "market_price": 100.0}},
                "score": {"total": 50},
                "references": {},
            },
        }
    )
    client = FakeRedisClient(publish_error=ConnectionError("redis down"))
    _install_cache(monkeypatch, JobCache(client, prev))
    current = {
        "coins": {"coin_emami": {"symbol": "IR_COIN_EMAMI", "market_price": 110.0}},
        "score": {"total": 50},
        "references": {},
    }

    signals = await detect_and_broadcast(current)

    # خطای Redis فقط publish را از کار می‌اندازد؛ job/سیگنال زنده می‌ماند.
    assert len(signals) == 1


# ── Subscriber (API process) ─────────────────────────────────


async def test_subscriber_forwards_signal_to_local_clients(monkeypatch) -> None:
    pubsub = FakePubSub(
        [
            _message({"type": "signal", "data": {"symbol": "X", "ts": TS}}),
            {"type": "subscribe", "channel": GOLD_WS_CHANNEL, "data": 1},
        ]
    )
    _install_cache(monkeypatch, FakeCache(FakeRedisClient(pubsub=pubsub)))

    hub = GoldWebSocketHub(snapshot_provider=_provider(None))
    ws = RecordingWS()
    hub._clients.add(ws)
    task = asyncio.create_task(hub._subscriber_loop())

    try:
        await asyncio.wait_for(ws.received.wait(), timeout=2)
        assert pubsub.channels == [GOLD_WS_CHANNEL]
        assert len(ws.messages) == 1
        frame = ws.messages[0]
        assert frame["type"] == "signal"
        assert frame["data"] == {"symbol": "X", "ts": TS}
        assert frame["as_of"] == TS_ISO
    finally:
        hub._stopping = True
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def test_subscriber_snapshot_ready_pushes_fresh_snapshot(monkeypatch) -> None:
    pubsub = FakePubSub([], block=False)
    _install_cache(monkeypatch, FakeCache(FakeRedisClient(pubsub=pubsub)))

    snap = _snapshot()
    hub = GoldWebSocketHub(snapshot_provider=_provider(snap))
    ws = RecordingWS()
    hub._clients.add(ws)

    await hub._handle_pubsub_message(
        _message({"type": "snapshot_ready", "as_of": "2026-01-01T00:00:00+00:00"})
    )

    assert len(ws.messages) == 1
    frame = ws.messages[0]
    assert frame["type"] == "snapshot"
    # as_of واقعی از snapshot خوانده می‌شود، نه از رویداد.
    assert frame["as_of"] == AS_OF
    assert frame["data"] == snap


async def test_subscriber_rejects_signal_without_as_of(monkeypatch) -> None:
    _install_cache(monkeypatch, FakeCache(FakeRedisClient()))
    hub = GoldWebSocketHub(snapshot_provider=_provider(None))
    ws = RecordingWS()
    hub._clients.add(ws)

    await hub._handle_pubsub_message(_message({"type": "signal", "data": {}}))

    assert ws.messages == []


async def test_subscriber_ignores_malformed_json(monkeypatch, caplog) -> None:
    _install_cache(monkeypatch, FakeCache(FakeRedisClient()))
    hub = GoldWebSocketHub(snapshot_provider=_provider(None))
    ws = RecordingWS()
    hub._clients.add(ws)

    with caplog.at_level("WARNING", logger=ws_hub_module.__name__):
        await hub._handle_pubsub_message(_message("{not-json"))

    assert ws.messages == []
    assert any("malformed JSON" in record.message for record in caplog.records)


async def test_subscriber_ignores_unknown_event_types(monkeypatch) -> None:
    _install_cache(monkeypatch, FakeCache(FakeRedisClient()))
    hub = GoldWebSocketHub(snapshot_provider=_provider(None))
    ws = RecordingWS()
    hub._clients.add(ws)

    await hub._handle_pubsub_message(
        _message({"type": "something_else", "as_of": AS_OF, "data": {}})
    )

    assert ws.messages == []


async def test_subscriber_reconnects_with_backoff(monkeypatch) -> None:
    client = FakeRedisClient(pubsub=ConnectionError("redis down"))
    _install_cache(monkeypatch, FakeCache(client))
    hub = GoldWebSocketHub()

    sleeps: list[float] = []

    async def _sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) >= 2:
            hub._stopping = True
        await asyncio.sleep(0)

    hub._sleep = _sleep

    await hub._subscriber_loop()

    assert sleeps == [SUBSCRIBER_BACKOFF_SECONDS, SUBSCRIBER_BACKOFF_SECONDS * 2]


async def test_subscriber_task_is_cancelled_by_stop(monkeypatch) -> None:
    pubsub = FakePubSub([], block=True)
    _install_cache(monkeypatch, FakeCache(FakeRedisClient(pubsub=pubsub)))

    hub = GoldWebSocketHub(
        hot_interval=3600.0,
        snapshot_interval=3600.0,
        hot_provider=_provider(None),
        snapshot_provider=_provider(None),
    )

    await hub.ensure_started()
    tasks = list(hub._tasks)
    await asyncio.sleep(0)

    assert len(tasks) == 3
    assert hub.is_running() is True

    await hub.stop()

    assert hub.is_running() is False
    assert all(task.cancelled() or task.done() for task in tasks)
    assert pubsub.closed is True


def test_channel_name_is_stable() -> None:
    assert GOLD_WS_CHANNEL == "golddesk:ws_events"


async def test_subscriber_accepts_bytes_messages_from_redis(monkeypatch) -> None:
    """کلاینت واقعی ``decode_responses=True`` است، ولی bytes هم نباید بشکند."""
    _install_cache(monkeypatch, FakeCache(FakeRedisClient()))
    hub = GoldWebSocketHub(snapshot_provider=_provider(None))
    ws = RecordingWS()
    hub._clients.add(ws)

    payload = {"type": "signal", "as_of": AS_OF, "data": {"symbol": "X", "ts": TS}}
    await hub._handle_pubsub_message(
        {"type": "message", "data": json.dumps(payload).encode("utf-8")}
    )

    assert len(ws.messages) == 1
    assert ws.messages[0]["as_of"] == AS_OF

