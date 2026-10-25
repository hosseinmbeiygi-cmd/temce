"""WebSocket Hub — پخش زندهٔ snapshot برای GoldDesk.

دو حلقهٔ مستقل (نه یک چرخهٔ مشترک):
- ``hot`` هر ۱۰ ثانیه، ساخته‌شده از ``hotpath.get_hot_snapshot()`` (Redis).
- ``snapshot`` هر ۳۰۰ ثانیه، خوانده‌شده از Redis (نه از حافظهٔ همین process).

به‌علاوه یک subscriber روی ``GOLD_WS_CHANNEL``: رویدادهای process job
(``signal``/``snapshot_ready``) را به کلاینت‌های همین process می‌رساند.

قواعد:
- هر پیام فیلد ``as_of`` دارد: زمان واقعی داده به شکل ISO UTC.
- اگر داده‌ای نباشد، هیچ پیامی فرستاده نمی‌شود (نه ``{}``).
- ارسال هر کلاینت timeout دارد؛ کلاینت کند حذف می‌شود و قفل hub در طول ارسال
  نگه داشته نمی‌شود تا یک کلاینت کند بقیه را بلاک نکند.
- taskها فقط وقتی event loop در حال اجراست ساخته می‌شوند (``ensure_started``).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from .hotpath import build_hotpath_response, get_hot_snapshot

logger = logging.getLogger(__name__)

HOT_INTERVAL_SECONDS = 10.0
SNAPSHOT_INTERVAL_SECONDS = 300.0
SEND_TIMEOUT_SECONDS = 5.0

# کانال مشترک job (scheduler/worker) و API؛ job در process دیگری اجرا می‌شود و
# کلاینت WebSocket ندارد، پس رویداد را از این کانال به API می‌رساند.
GOLD_WS_CHANNEL = "golddesk:ws_events"
# بازهٔ تلاش دوبارهٔ subscriber؛ نمایی و سقف‌دار (ثانیه).
SUBSCRIBER_BACKOFF_SECONDS = 1.0
SUBSCRIBER_BACKOFF_MAX_SECONDS = 30.0

SnapshotProvider = Callable[[], Awaitable[dict[str, Any] | None]]
Sleep = Callable[[float], Awaitable[None]]


def _iso_utc(value: Any) -> str | None:
    """تبدیل زمان داده به ISO UTC؛ None یعنی زمان معتبری وجود ندارد."""
    if isinstance(value, str):
        return value or None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value > 0:
        try:
            return datetime.fromtimestamp(float(value), UTC).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def payload_as_of(payload: dict[str, Any] | None) -> str | None:
    """زمان واقعی داده: ``as_of``/``snapshot_at`` در ریشه یا درون ``data``.

    snapshot خام Redis فیلد ``snapshot_at`` را در ریشه دارد و پیام آمادهٔ ارسال
    ``as_of``؛ سیگنال‌ها زمان epoch را در ``data.ts`` می‌گذارند.
    """
    if not isinstance(payload, dict):
        return None
    direct = _iso_utc(payload.get("as_of")) or _iso_utc(payload.get("snapshot_at"))
    if direct:
        return direct
    data = payload.get("data")
    if isinstance(data, dict):
        return (
            _iso_utc(data.get("snapshot_at"))
            or _iso_utc(data.get("as_of"))
            or _iso_utc(data.get("ts"))
        )
    return None


def with_as_of(payload: dict[str, Any]) -> dict[str, Any] | None:
    """نسخه‌ای از پیام که فیلد ``as_of`` دارد؛ None یعنی دادهٔ زمان‌دار نیست."""
    as_of = payload_as_of(payload)
    if as_of is None:
        return None
    enriched = dict(payload)
    enriched["as_of"] = as_of
    return enriched


async def _redis_snapshot() -> dict[str, Any] | None:
    """snapshot منتشرشده در Redis؛ در صورت نبود/خطا None."""
    return await get_hot_snapshot()


async def publish_ws_event(payload: dict[str, Any]) -> bool:
    """انتشار یک رویداد WS در Redis برای process API.

    از همان کلاینت async و همان کانفیگ ``core.cache`` استفاده می‌کند. نبود Redis،
    نبود ``as_of`` یا هر خطای انتشار فقط لاگ/``False`` است و job را نمی‌شکند.
    """
    message = with_as_of(payload)
    if message is None:
        logger.debug("WS publish skipped: payload has no data timestamp")
        return False
    try:
        from core.cache import get_cache

        client = get_cache().client
        if client is None:
            logger.warning("WS publish skipped: Redis is unavailable")
            return False
        await client.publish(GOLD_WS_CHANNEL, json.dumps(message, default=str))
        return True
    except Exception as exc:  # noqa: BLE001 — job نباید به‌خاطر Redis بمیرد
        logger.warning("WS publish failed: %s", type(exc).__name__)
        return False


class GoldWebSocketHub:
    """Hub برای پخش زندهٔ snapshot و hot path."""

    def __init__(
        self,
        *,
        hot_interval: float = HOT_INTERVAL_SECONDS,
        snapshot_interval: float = SNAPSHOT_INTERVAL_SECONDS,
        send_timeout: float = SEND_TIMEOUT_SECONDS,
        hot_provider: SnapshotProvider | None = None,
        snapshot_provider: SnapshotProvider | None = None,
        sleep: Sleep | None = None,
    ) -> None:
        self._clients: set[Any] = set()
        self._lock = asyncio.Lock()
        self._last_snapshot: dict[str, Any] | None = None

        self._hot_interval = hot_interval
        self._snapshot_interval = snapshot_interval
        self._send_timeout = send_timeout
        # منبع hot و snapshot هر دو Redis است؛ job ممکن است در process دیگری
        # اجرا شود، پس حافظهٔ محلی فقط fallback است.
        self._hot_provider: SnapshotProvider = hot_provider or _redis_snapshot
        self._snapshot_provider: SnapshotProvider = snapshot_provider or _redis_snapshot
        self._sleep: Sleep = sleep or asyncio.sleep

        self._tasks: list[asyncio.Task[None]] = []
        self._stopping = False

    # ── Clients ──────────────────────────────────────────────

    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)
        logger.info("GoldDesk WS client connected (total: %d)", self.client_count())
        cached = await self._snapshot_message()
        if cached is not None:
            await self._send(ws, cached, drop_on_fail=True)

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("GoldDesk WS client disconnected (total: %d)", self.client_count())

    def cache_snapshot(self, snap_dict: dict[str, Any]) -> None:
        """نگه‌داشتن آخرین snapshot در همین process (fallback وقتی Redis نیست)."""
        self._last_snapshot = snap_dict

    async def _clients_snapshot(self) -> list[Any]:
        async with self._lock:
            return list(self._clients)

    async def _drop(self, ws: Any) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("GoldDesk WS client dropped (total: %d)", self.client_count())

    # ── Redis pub/sub ────────────────────────────────────────

    async def _subscriber_loop(self) -> None:
        """دریافت رویدادهای job از Redis و پخش در همین process.

        اتصال با backoff نمایی دوباره برقرار می‌شود؛ توقف با cancel شدن task.
        """
        backoff = SUBSCRIBER_BACKOFF_SECONDS
        while not self._stopping:
            pubsub = None
            try:
                from core.cache import get_cache

                client = get_cache().client
                if client is None:
                    raise RuntimeError("Redis client is unavailable")
                pubsub = client.pubsub()
                await pubsub.subscribe(GOLD_WS_CHANNEL)
                backoff = SUBSCRIBER_BACKOFF_SECONDS
                logger.info("GoldDesk WS subscribed to %s", GOLD_WS_CHANNEL)
                async for message in pubsub.listen():
                    if self._stopping:
                        return
                    await self._handle_pubsub_message(message)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 — با backoff دوباره وصل می‌شویم
                logger.warning(
                    "GoldDesk WS subscriber disconnected: %s", type(exc).__name__
                )
            finally:
                if pubsub is not None:
                    with contextlib.suppress(Exception):
                        await pubsub.aclose()
            if self._stopping:
                break
            await self._sleep(backoff)
            backoff = min(backoff * 2, SUBSCRIBER_BACKOFF_MAX_SECONDS)

    async def _handle_pubsub_message(self, message: Any) -> None:
        """یک پیام Redis را به فریم WS تبدیل می‌کند (شکل فریم‌ها تغییر نمی‌کند)."""
        if not isinstance(message, dict) or message.get("type") != "message":
            return
        raw = message.get("data")
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        if not isinstance(raw, str):
            logger.warning("GoldDesk WS pub/sub: non-text message ignored")
            return
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            logger.warning("GoldDesk WS pub/sub: malformed JSON ignored")
            return
        if not isinstance(payload, dict):
            logger.warning("GoldDesk WS pub/sub: non-object payload ignored")
            return
        if payload_as_of(payload) is None:
            logger.debug("GoldDesk WS pub/sub: payload without as_of ignored")
            return
        if payload.get("type") == "snapshot_ready":
            # snapshot تازه از همان مسیر Redis/hotpath خوانده می‌شود تا as_of
            # واقعی باشد، نه زمان رویداد.
            try:
                snapshot_message = await self._snapshot_message()
            except Exception as exc:  # noqa: BLE001 — subscriber نباید بمیرد
                logger.warning("snapshot refresh failed: %s", type(exc).__name__)
                return
            if snapshot_message is not None:
                await self.broadcast(snapshot_message)
            return
        if payload.get("type") != "signal":
            logger.debug(
                "GoldDesk WS pub/sub: unknown event type %r ignored", payload.get("type")
            )
            return
        await self.broadcast(payload)

    # ── Send ─────────────────────────────────────────────────

    async def _send(self, ws: Any, payload: dict[str, Any], *, drop_on_fail: bool) -> bool:
        """ارسال با timeout؛ قفل hub اینجا گرفته نمی‌شود."""
        try:
            await asyncio.wait_for(ws.send_json(payload), timeout=self._send_timeout)
            return True
        except Exception as exc:  # noqa: BLE001 — خطای یک کلاینت فقط همان را حذف می‌کند
            logger.warning("GoldDesk WS send failed (%s)", type(exc).__name__)
            if drop_on_fail:
                await self._drop(ws)
            return False

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """پخش پیام به همهٔ subscribers؛ ارسال‌ها هم‌زمان و بیرون از قفل."""
        message = with_as_of(payload)
        if message is None:
            logger.debug("WS broadcast skipped: payload has no data timestamp")
            return
        clients = await self._clients_snapshot()
        if not clients:
            return
        results = await asyncio.gather(
            *(self._send(ws, message, drop_on_fail=False) for ws in clients),
            return_exceptions=True,
        )
        for ws, ok in zip(clients, results):
            if ok is not True:
                await self._drop(ws)

    # ── Payload builders ─────────────────────────────────────

    async def _hot_message(self) -> dict[str, Any] | None:
        snap = await self._hot_provider()
        as_of = payload_as_of(snap)
        if as_of is None:
            return None
        data = build_hotpath_response(snap).get("data") or {}
        if data.get("status") != "ok":
            return None
        return {"type": "hot", "as_of": as_of, "data": data}

    async def _snapshot_message(self) -> dict[str, Any] | None:
        snap = await self._snapshot_provider()
        if not snap:
            # Redis خالی است — فقط اگر همین process snapshot را cache کرده باشد.
            snap = self._last_snapshot
        as_of = payload_as_of(snap)
        if as_of is None:
            return None
        return {"type": "snapshot", "as_of": as_of, "data": snap}

    # ── Loops ────────────────────────────────────────────────

    async def _hot_loop(self) -> None:
        while not self._stopping:
            await self._sleep(self._hot_interval)
            if self._stopping:
                break
            if self.client_count() == 0:
                continue
            try:
                message = await self._hot_message()
            except Exception as exc:  # noqa: BLE001 — حلقه نباید بمیرد
                logger.warning("hot build failed: %s", type(exc).__name__)
                continue
            if message is not None:
                await self.broadcast(message)

    async def _snapshot_loop(self) -> None:
        while not self._stopping:
            await self._sleep(self._snapshot_interval)
            if self._stopping:
                break
            if self.client_count() == 0:
                continue
            try:
                message = await self._snapshot_message()
            except Exception as exc:  # noqa: BLE001 — حلقه نباید بمیرد
                logger.warning("snapshot build failed: %s", type(exc).__name__)
                continue
            if message is not None:
                await self.broadcast(message)

    # ── Lifecycle ────────────────────────────────────────────

    def is_running(self) -> bool:
        return bool(self._tasks) and not all(t.done() for t in self._tasks)

    async def ensure_started(self) -> None:
        """شروع حلقه‌ها؛ فقط از داخل event loop در حال اجرا صدا زده می‌شود."""
        if self.is_running():
            return
        self._stopping = False
        loop = asyncio.get_running_loop()
        self._tasks = [
            loop.create_task(self._hot_loop(), name="golddesk-ws-hot"),
            loop.create_task(self._snapshot_loop(), name="golddesk-ws-snapshot"),
            loop.create_task(self._subscriber_loop(), name="golddesk-ws-subscriber"),
        ]
        logger.info("GoldDesk WS broadcast loops + pub/sub subscriber started")

    async def stop(self) -> None:
        """توقف تمیز حلقه‌ها (shutdown یا تست)."""
        self._stopping = True
        tasks = self._tasks
        self._tasks = []
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


# Singleton
_hub: GoldWebSocketHub | None = None


def get_hub() -> GoldWebSocketHub:
    """Singleton بدون ساخت task — شروع کار با ``ensure_started`` در event loop."""
    global _hub
    if _hub is None:
        _hub = GoldWebSocketHub()
    return _hub


async def ws_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint — پخش زندهٔ snapshot."""
    await websocket.accept()
    hub = get_hub()
    await hub.ensure_started()
    await hub.register(websocket)

    try:
        while True:
            # پیام کلاینت (ping/pong)
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await hub.unregister(websocket)
    except Exception as exc:  # noqa: BLE001
        logger.warning("GoldDesk WS error: %s", type(exc).__name__)
        await hub.unregister(websocket)
