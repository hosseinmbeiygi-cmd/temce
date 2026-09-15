"""
Realtime Service - WebSocket-based live market data broadcasting.

Broadcasts price updates to connected WebSocket clients via Redis Pub/Sub.
Works across multiple backend instances.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from core.cache import get_cache
from core.logging import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, set[str]] = {}  # symbol -> set of connection IDs
        self._conn_subscriptions: dict[str, set[str]] = {}  # connection ID -> set of symbols
        self._lock = asyncio.Lock()

    @property
    def total_connections(self) -> int:
        return len(self._conn_subscriptions)

    async def connect(self, connection_id: str, symbols: list[str] | None = None) -> None:
        async with self._lock:
            self._conn_subscriptions[connection_id] = set(symbols or [])
            for sym in symbols or []:
                self._connections.setdefault(sym, set()).add(connection_id)

    async def disconnect(self, connection_id: str) -> None:
        async with self._lock:
            subs = self._conn_subscriptions.pop(connection_id, set())
            for sym in subs:
                conns = self._connections.get(sym, set())
                conns.discard(connection_id)
                if not conns:
                    self._connections.pop(sym, None)

    async def subscribe(self, connection_id: str, symbols: list[str]) -> None:
        async with self._lock:
            existing = self._conn_subscriptions.get(connection_id, set())
            for sym in symbols:
                existing.add(sym)
                self._connections.setdefault(sym, set()).add(connection_id)
            self._conn_subscriptions[connection_id] = existing

    async def unsubscribe(self, connection_id: str, symbols: list[str]) -> None:
        async with self._lock:
            existing = self._conn_subscriptions.get(connection_id, set())
            for sym in symbols:
                existing.discard(sym)
                conns = self._connections.get(sym, set())
                conns.discard(connection_id)
                if not conns:
                    self._connections.pop(sym, None)
            self._conn_subscriptions[connection_id] = existing

    async def get_subscribers(self, symbol: str) -> set[str]:
        return self._connections.get(symbol, set()).copy()


class RealtimeService:
    """Broadcasts live market data to WebSocket clients."""

    def __init__(self) -> None:
        self.manager = ConnectionManager()
        self._running = False
        self._poll_task: asyncio.Task | None = None
        self._redis_sub_task: asyncio.Task | None = None
        self._client_callbacks: dict[str, Any] = {}  # connection_id -> websocket.send
        self._POLL_INTERVAL = 3.0  # seconds between price polls during market hours
        self._CACHE_KEY_PREFIX = "realtime:prices"
        self._PUBSUB_CHANNEL = "realtime:price_updates:v1"
        self._instance_id = uuid.uuid4().hex[:12]
        self._pubsub: Any = None

    async def start(self) -> None:
        """Start the realtime service background tasks."""
        if self._running:
            return
        cache = get_cache()
        await cache.initialize()
        self._running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        self._redis_sub_task = asyncio.create_task(self._redis_listener())
        logger.info("RealtimeService started (poll=%ss)", self._POLL_INTERVAL)

    async def stop(self) -> None:
        self._running = False
        for task in (self._poll_task, self._redis_sub_task):
            if task:
                task.cancel()
        for task in (self._poll_task, self._redis_sub_task):
            if task:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._poll_task = None
        self._redis_sub_task = None
        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(self._PUBSUB_CHANNEL)
                await self._pubsub.close()
            except Exception:
                logger.debug("Failed to close realtime Redis pubsub", exc_info=True)
            self._pubsub = None
        logger.info("RealtimeService stopped")

    async def register_client(self, connection_id: str, send_fn: Any, symbols: list[str] | None = None) -> None:
        self._client_callbacks[connection_id] = send_fn
        await self.manager.connect(connection_id, symbols)
        logger.info("Client %s registered (%d symbols)", connection_id, len(symbols or []))

    async def unregister_client(self, connection_id: str) -> None:
        self._client_callbacks.pop(connection_id, None)
        await self.manager.disconnect(connection_id)

    async def handle_message(self, connection_id: str, raw: str) -> None:
        try:
            msg = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            await self._send_to(connection_id, {"error": "invalid JSON"})
            return

        action = msg.get("action")
        if action == "subscribe":
            symbols = msg.get("symbols", [])
            if isinstance(symbols, str):
                symbols = [symbols]
            await self.manager.subscribe(connection_id, symbols)
            await self._send_to(connection_id, {"action": "subscribed", "symbols": symbols})
        elif action == "unsubscribe":
            symbols = msg.get("symbols", [])
            if isinstance(symbols, str):
                symbols = [symbols]
            await self.manager.unsubscribe(connection_id, symbols)
            await self._send_to(connection_id, {"action": "unsubscribed", "symbols": symbols})
        elif action == "ping":
            pong = {"action": "pong", "ts": time.time()}
            if msg.get("client_ts") is not None:
                pong["client_ts"] = msg["client_ts"]
            await self._send_to(connection_id, pong)
        else:
            await self._send_to(connection_id, {"error": f"unknown action: {action}"})

    async def broadcast_price(self, symbol: str, data: dict[str, Any]) -> None:
        """Broadcast a price update to local subscribers only."""
        cache = get_cache()
        cache_key = f"{self._CACHE_KEY_PREFIX}:{symbol}"
        await cache.set(cache_key, data, ttl=30)

        subscribers = await self.manager.get_subscribers(symbol)
        if not subscribers:
            return

        payload = {"action": "price", "symbol": symbol, **data}
        msg = json.dumps(payload, default=str)

        for conn_id in subscribers:
            send_fn = self._client_callbacks.get(conn_id)
            if send_fn:
                try:
                    await send_fn(msg)
                except Exception:
                    await self.unregister_client(conn_id)

    async def publish_price(self, symbol: str, data: dict[str, Any]) -> None:
        """Persist, publish and locally broadcast one canonical price event.

        The ``source_instance`` field prevents the publishing process from
        delivering its own Redis message a second time through the listener.
        """
        cache = get_cache()
        cache_key = f"{self._CACHE_KEY_PREFIX}:{symbol}"
        await cache.set(cache_key, data, ttl=30)
        payload = {
            "v": 1,
            "event": "price_update",
            "source_instance": self._instance_id,
            "published_at": time.time(),
            "symbol": symbol,
            "data": data,
        }
        if cache._redis:
            try:
                await cache._redis.publish(self._PUBSUB_CHANNEL, json.dumps(payload, default=str))
            except Exception:
                logger.warning("Redis publish failed for %s; local broadcast continues", symbol, exc_info=True)
        await self._broadcast_local(symbol, data)

    async def _broadcast_local(self, symbol: str, data: dict[str, Any]) -> None:
        subscribers = await self.manager.get_subscribers(symbol)
        if not subscribers:
            return
        payload = {"action": "price", "symbol": symbol, **data}
        msg = json.dumps(payload, default=str)
        for conn_id in subscribers:
            send_fn = self._client_callbacks.get(conn_id)
            if send_fn:
                try:
                    await send_fn(msg)
                except Exception:
                    await self.unregister_client(conn_id)

    async def _send_to(self, connection_id: str, data: dict[str, Any]) -> None:
        send_fn = self._client_callbacks.get(connection_id)
        if send_fn:
            try:
                await send_fn(json.dumps(data, default=str))
            except Exception:
                await self.unregister_client(connection_id)

    async def _poll_loop(self) -> None:
        """Periodically fetch prices for subscribed symbols and broadcast."""
        while self._running:
            try:
                await asyncio.sleep(self._POLL_INTERVAL)
                all_symbols = set()
                for subs in self.manager._connections.values():
                    all_symbols.update(subs)
                if not all_symbols:
                    continue

                cache = get_cache()
                for symbol in all_symbols:
                    cached = await cache.get(f"quote:latest:{symbol}")
                    if cached:
                        await self.publish_price(symbol, cached)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("RealtimeService poll error")
                await asyncio.sleep(5)

    async def _redis_listener(self) -> None:
        """Listen for price updates from other instances via Redis Pub/Sub."""
        while self._running:
            pubsub = None
            try:
                cache = get_cache()
                await cache.initialize()
                if not cache._redis:
                    logger.info("Redis not available, retrying cross-instance pub/sub")
                    await asyncio.sleep(5)
                    continue

                pubsub = cache._redis.pubsub()
                self._pubsub = pubsub
                await pubsub.subscribe(self._PUBSUB_CHANNEL)

                async for message in pubsub.listen():
                    if not self._running:
                        break
                    if message["type"] != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                        if not isinstance(data, dict):
                            continue
                        # Ignore our own publish: it was already sent locally.
                        if data.get("source_instance") == self._instance_id:
                            continue
                        if data.get("event") == "price_update":
                            symbol = data.get("symbol")
                            price_data = data.get("data") or {}
                            if symbol:
                                await self._broadcast_local(symbol, price_data)
                        else:
                            # Backward-compatible reader for legacy map payloads.
                            for symbol, price_data in data.items():
                                if isinstance(price_data, dict):
                                    await self._broadcast_local(symbol, price_data)
                    except Exception as e:
                        logger.debug("Failed to process Redis message: %s", e)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Redis listener disconnected; retrying", exc_info=True)
                await asyncio.sleep(5)
            finally:
                self._pubsub = None
                if pubsub is not None:
                    try:
                        await pubsub.close()
                    except Exception:
                        pass


_realtime_service: RealtimeService | None = None


def get_realtime_service() -> RealtimeService:
    global _realtime_service
    if _realtime_service is None:
        _realtime_service = RealtimeService()
    return _realtime_service
