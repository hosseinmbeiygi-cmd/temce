from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


try:
    import websockets

    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class BaseWebSocketClient:
    def __init__(self, url: str, ping_interval: int = 20, ping_timeout: int = 10) -> None:
        self.url = url
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self._ws: Any = None
        self._connected: bool = False
        self._listeners: dict[str, list[Callable]] = {}
        self._reconnect_task: asyncio.Task | None = None

    async def connect(self) -> bool:
        if not HAS_WEBSOCKETS:
            logger.error("websockets library not installed")
            return False
        try:
            self._ws = await websockets.connect(
                self.url,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
            )
            self._connected = True
            logger.info("WebSocket connected to %s", self.url)
            return True
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        self._connected = False
        if self._ws:
            await self._ws.close()
            self._ws = None
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

    async def send(self, message: dict[str, Any]) -> bool:
        if not self._connected or not self._ws:
            return False
        try:
            await self._ws.send(json.dumps(message))
            return True
        except Exception as e:
            logger.error("WebSocket send failed: %s", e)
            return False

    async def receive(self) -> dict[str, Any] | None:
        if not self._connected or not self._ws:
            return None
        try:
            message = await self._ws.recv()
            return json.loads(message) if isinstance(message, str) else message
        except Exception as e:
            logger.error("WebSocket receive failed: %s", e)
            return None

    async def listen(self, handler: Callable) -> None:
        while self._connected:
            message = await self.receive()
            if message:
                await handler(message)

    def is_connected(self) -> bool:
        return self._connected
