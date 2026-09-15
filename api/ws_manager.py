"""
Armor WebSocket Manager — api/ws_manager.py
===========================================
Real-time progress broadcasting for the Armor Dashboard precomputation.

- Manages WebSocket connections at /api/v1/ws/precompute
- Broadcasts the 4 events from contracts/events.md:
    1. PRECOMPUTATION_PROGRESS
    2. PRECOMPUTATION_GROUP_COMPLETED
    3. PRECOMPUTATION_COMPLETED
    4. SYMBOL_RESULT_UPDATED
- Also broadcasts via Redis Pub/Sub for multi-worker fan-out (fallback to in-memory when Redis unavailable).
- Decoupled: never imports from ingestion / precompute / frontend — only contracts + core.cache.

Reuse: pattern from apps/api/endpoints/websocket.py (market WS) + services/realtime_service.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections import deque
from typing import Any

from fastapi import WebSocket

from core.logging import get_logger

logger = get_logger(__name__)

# ── Event type constants (contracts/events.md) ──────────────────
EVENT_PROGRESS = "PRECOMPUTATION_PROGRESS"
EVENT_GROUP_COMPLETED = "PRECOMPUTATION_GROUP_COMPLETED"
EVENT_COMPLETED = "PRECOMPUTATION_COMPLETED"
EVENT_SYMBOL_UPDATED = "SYMBOL_RESULT_UPDATED"

# Legacy in-process channel + the precompute workers' contract channel
# (precompute/config.py).  Both are consumed so events reach the funnel
# regardless of which side's default the publisher used.
REDIS_CHANNEL = "armor:events"
REDIS_CHANNEL_PRECOMPUTE = "precompute:events"
REDIS_STATUS_KEY = "armor:precompute:status"
REDIS_RESULTS_HASH = "armor:precompute:results"  # hash symbol -> JSON

# Worker event types that feed the job state machine (mirror of
# api.job_state.STATE_EVENT_TYPES — imported lazily to avoid a module cycle).
_STATE_EVENT_TYPES: frozenset[str] | None = None


def _state_event_types() -> frozenset[str]:
    global _STATE_EVENT_TYPES
    if _STATE_EVENT_TYPES is None:
        try:
            from api.job_state import STATE_EVENT_TYPES

            _STATE_EVENT_TYPES = STATE_EVENT_TYPES
        except Exception:
            _STATE_EVENT_TYPES = frozenset()
    return _STATE_EVENT_TYPES


class ArmorWsManager:
    """
    In-process WS connection registry + Redis pub/sub fan-out.

    Usage in a FastAPI router:

        manager = get_armor_ws_manager()

        @router.websocket("/precompute")
        async def ws_precompute(ws: WebSocket):
            await manager.connect(ws)
            try:
                while True:
                    await ws.receive_text()  # keep-alive / client ping
            except WebSocketDisconnect:
                pass
            finally:
                await manager.disconnect(ws)

        # From precompute_router / Celery callbacks:
        await manager.broadcast_progress({...})
        await manager.broadcast_completed({...})
    """

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._subscriber_task: asyncio.Task[Any] | None = None
        self._running = False
        # Dedupe window: in-process broadcasts are also published to Redis,
        # and this process's own subscriber receives that echo.  Exactly-once
        # delivery per event_id (worker publishes absolute counters, but the
        # funnel should still not process the same event twice).
        self._seen_event_ids: set[str] = set()
        self._recent_event_ids: deque[str] = deque(maxlen=1024)
        # Strong refs to fire-and-forget broadcast tasks (GC protection).
        self._pending_tasks: set[asyncio.Task[None]] = set()

    # ── Connection lifecycle ─────────────────────────────────────
    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        conn_id = str(uuid.uuid4())[:8]
        async with self._lock:
            self._connections.add(websocket)
        logger.info("Armor WS connected: %s (total=%d)", conn_id, len(self._connections))
        # Immediately push current status so the client can hydrate without an extra REST call
        try:
            status = await self._load_status_snapshot()
            if status:
                await self._send(
                    websocket,
                    {"type": "PRECOMPUTATION_STATUS_SNAPSHOT", "payload": status},
                )
        except Exception:
            logger.debug("Armor WS snapshot push failed", exc_info=True)
        # Ensure Redis subscriber is running (multi-worker fan-out)
        await self._ensure_subscriber()
        return conn_id

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)
        logger.info("Armor WS disconnected (remaining=%d)", len(self._connections))

    # ── Low-level send ───────────────────────────────────────────
    def _mark_seen(self, event_id: str | None) -> bool:
        """True on first sight, False for a duplicate delivery.

        Bounded ring: when the window is full the oldest id is evicted from
        both structures together, so neither can grow unbounded.
        """
        if not event_id:
            return True
        if event_id in self._seen_event_ids:
            return False
        recent = self._recent_event_ids
        while len(recent) >= recent.maxlen or len(self._seen_event_ids) >= 1024:
            if not recent:
                break
            self._seen_event_ids.discard(recent.popleft())
        self._seen_event_ids.add(event_id)
        recent.append(event_id)
        return True

    async def _send(self, ws: WebSocket, data: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(data, ensure_ascii=False, default=str))
        except Exception:
            # Broken connection — will be pruned on next broadcast
            pass

    async def _broadcast(self, data: dict[str, Any]) -> None:
        # Dedupe: the Redis echo of our own publish arrives through the
        # subscriber with the same event_id — deliver exactly once.
        event_id = data.get("event_id") or uuid.uuid4().hex[:16]
        data["event_id"] = event_id
        if not self._mark_seen(event_id):
            return

        event_type = data.get("type")
        payload = data.get("payload")

        text = json.dumps(data, ensure_ascii=False, default=str)
        async with self._lock:
            conns = list(self._connections)

        # Send to connected clients FIRST so consumers observe the raw worker
        # event before the recomputed snapshot it triggers.
        if conns:
            dead: list[WebSocket] = []
            for ws in conns:
                try:
                    await ws.send_text(text)
                except Exception:
                    dead.append(ws)
            if dead:
                async with self._lock:
                    for ws in dead:
                        self._connections.discard(ws)

        # Then feed the shared job state machine (api/job_state.py) so that
        # /precompute/status reflects real worker progress.  This is the single
        # funnel point through which every worker event passes, whether it was
        # published in-process or via the Redis armor:events channel.
        #
        # Only the 4 contract worker events may enter the state machine —
        # derived events (PRECOMPUTATION_STATUS_SNAPSHOT, emitted by job_state
        # itself) are excluded by the whitelist, preventing recursion.  State
        # updates still run when no clients are connected.
        if (
            isinstance(event_type, str)
            and isinstance(payload, dict)
            and event_type in _state_event_types()
        ):
            try:
                from api.job_state import handle_event

                await handle_event(event_type, payload)
            except Exception:
                logger.debug("job_state handle_event failed for %s", event_type, exc_info=True)

    # ── Public broadcast helpers (called by Celery / API) ────────
    async def broadcast_progress(self, payload: dict[str, Any]) -> None:
        """Broadcast PRECOMPUTATION_PROGRESS."""
        event = {"type": EVENT_PROGRESS, "payload": payload, "ts": time.time()}
        await self._publish(event)
        await self._broadcast(event)

    async def broadcast_group_completed(self, payload: dict[str, Any]) -> None:
        """Broadcast PRECOMPUTATION_GROUP_COMPLETED."""
        event = {"type": EVENT_GROUP_COMPLETED, "payload": payload, "ts": time.time()}
        await self._publish(event)
        await self._broadcast(event)

    async def broadcast_completed(self, payload: dict[str, Any]) -> None:
        """Broadcast PRECOMPUTATION_COMPLETED — triggers frontend SoundEffectManager."""
        event = {"type": EVENT_COMPLETED, "payload": payload, "ts": time.time()}
        await self._publish(event)
        await self._broadcast(event)

    async def broadcast_symbol_updated(self, payload: dict[str, Any]) -> None:
        """Broadcast SYMBOL_RESULT_UPDATED."""
        event = {"type": EVENT_SYMBOL_UPDATED, "payload": payload, "ts": time.time()}
        await self._publish(event)
        await self._broadcast(event)

    async def broadcast_raw(self, event_type: str, payload: dict[str, Any]) -> None:
        """Generic broadcast for any event type."""
        event = {"type": event_type, "payload": payload, "ts": time.time()}
        await self._publish(event)
        await self._broadcast(event)

    # ── Sync entry point for precompute workers (API callback) ───
    def broadcast_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """
        Synchronous callback surface for the precompute module.

        Called by precompute.workers.celery_tasks._emit when it detects a
        running loop (sync-fallback pipeline inside the API process).
        Schedules the full broadcast — Redis fan-out, WebSocket delivery,
        and the job_state funnel — without blocking the caller.  Raises
        RuntimeError when no loop is running; the caller falls back to its
        own Redis transport in that case.
        """
        loop = asyncio.get_running_loop()  # RuntimeError propagates by design
        event = {"type": event_type, "payload": payload, "ts": time.time()}
        task = loop.create_task(self._publish_and_broadcast(event))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def broadcast_event_awaited(self, event_type: str, payload: dict[str, Any]) -> None:
        """Awaitable twin of ``broadcast_event`` for async callers (the async
        dispatch path): guarantees the event has fully traversed the funnel
        (Redis fan-out + WS delivery + job_state) before returning."""
        event = {"type": event_type, "payload": payload, "ts": time.time()}
        await self._publish(event)
        await self._broadcast(event)

    async def _publish_and_broadcast(self, event: dict[str, Any]) -> None:
        await self._publish(event)
        await self._broadcast(event)

    # ── Redis Pub/Sub fan-out (multi-worker) ─────────────────────
    async def start_subscriber(self) -> None:
        """Public startup hook: begin consuming armor:events.

        Called from the app lifespan so cross-process events (real Celery
        workers publishing via sync Redis) reach the job_state funnel even
        when no WebSocket client has ever connected.
        """
        await self._ensure_subscriber()

    async def _publish(self, event: dict[str, Any]) -> None:
        """Publish to Redis so other workers can fan-out to their own clients."""
        try:
            from core.cache import get_cache

            cache = get_cache()
            if cache.is_connected and cache.client is not None:
                event.setdefault("event_id", uuid.uuid4().hex[:16])
                await cache.client.publish(REDIS_CHANNEL, json.dumps(event, ensure_ascii=False, default=str))
        except Exception:
            logger.debug("Armor WS Redis publish failed", exc_info=True)

    async def _ensure_subscriber(self) -> None:
        if self._subscriber_task is not None and not self._subscriber_task.done():
            return
        try:
            from core.cache import get_cache

            cache = get_cache()
            if not cache.is_connected or cache.client is None:
                return
            self._subscriber_task = asyncio.create_task(self._subscriber_loop(), name="armor-ws-subscriber")
        except Exception:
            logger.debug("Armor WS subscriber start failed", exc_info=True)

    async def _subscriber_loop(self) -> None:
        try:
            from core.cache import get_cache

            cache = get_cache()
            client = cache.client
            if client is None:
                return
            pubsub = client.pubsub()
            await pubsub.subscribe(REDIS_CHANNEL, REDIS_CHANNEL_PRECOMPUTE)
            logger.info(
                "Armor WS subscribed to Redis channels: %s, %s",
                REDIS_CHANNEL,
                REDIS_CHANNEL_PRECOMPUTE,
            )
            async for message in pubsub.listen():
                if message.get("type") != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    await self._broadcast(data)
                except Exception:
                    logger.debug("Armor WS subscriber message parse failed", exc_info=True)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.debug("Armor WS subscriber loop exited", exc_info=True)

    async def _load_status_snapshot(self) -> dict[str, Any] | None:
        try:
            from api.job_state import load_status

            # Shared state machine (memory fallback works without Redis too)
            status = await load_status()
            if isinstance(status, dict) and status.get("overall_status"):
                return status
        except Exception:
            pass
        try:
            from core.cache import get_cache

            cache = get_cache()
            if cache.is_connected:
                raw = await cache.get(REDIS_STATUS_KEY)
                if isinstance(raw, dict):
                    return raw
                if isinstance(raw, str):
                    return json.loads(raw)
        except Exception:
            pass
        return None

    def connection_count(self) -> int:
        return len(self._connections)

    async def shutdown(self) -> None:
        if self._subscriber_task is not None:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass
            self._subscriber_task = None
        async with self._lock:
            for ws in list(self._connections):
                try:
                    await ws.close(code=1001)
                except Exception:
                    pass
            self._connections.clear()


# ── Singleton ────────────────────────────────────────────────────
_manager: ArmorWsManager | None = None


def get_armor_ws_manager() -> ArmorWsManager:
    global _manager
    if _manager is None:
        _manager = ArmorWsManager()
    return _manager
