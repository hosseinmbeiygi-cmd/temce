"""WebSocket Hub — پخش زنده snapshot.

هر 5 ثانیه (FE درخواست) snapshot جدید می‌سازد و به همه subscribers push می‌کند.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class GoldWebSocketHub:
    """Hub برای پخش زنده gold snapshot."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._last_snapshot: dict[str, Any] | None = None
        self._task: asyncio.Task | None = None

    async def register(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)
        logger.info("GoldDesk WS client connected (total: %d)", len(self._clients))
        if self._last_snapshot:
            with contextlib.suppress(Exception):
                await ws.send_json({"type": "snapshot", "data": self._last_snapshot})

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)
        logger.info("GoldDesk WS client disconnected (total: %d)", len(self._clients))

    async def broadcast(self, payload: dict[str, Any]) -> None:
        """پخش پیام به همه subscribers."""
        async with self._lock:
            stale: list[WebSocket] = []
            for ws in self._clients:
                try:
                    await ws.send_json(payload)
                except Exception:
                    stale.append(ws)
            for ws in stale:
                self._clients.discard(ws)

    def cache_snapshot(self, snap_dict: dict[str, Any]) -> None:
        """cache آخرین snapshot برای client‌های جدید."""
        self._last_snapshot = snap_dict

    def client_count(self) -> int:
        return len(self._clients)


# Singleton
_hub: GoldWebSocketHub | None = None


def get_hub() -> GoldWebSocketHub:
    global _hub
    if _hub is None:
        _hub = GoldWebSocketHub()
    return _hub


async def ws_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint — پخش زنده snapshot."""
    await websocket.accept()
    hub = get_hub()
    await hub.register(websocket)

    try:
        while True:
            # منتظر پیام از client (ping/pong)
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await hub.unregister(websocket)
    except Exception as exc:
        logger.warning("GoldDesk WS error: %s", exc)
        await hub.unregister(websocket)
