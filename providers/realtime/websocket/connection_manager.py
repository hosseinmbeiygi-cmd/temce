from __future__ import annotations

import asyncio
from typing import Any

from core.logging import get_logger
from providers.realtime.websocket.base_ws_client import BaseWebSocketClient

logger = get_logger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, BaseWebSocketClient] = {}
        self._lock = asyncio.Lock()

    async def register(self, name: str, client: BaseWebSocketClient) -> None:
        async with self._lock:
            self._connections[name] = client
            logger.info("Registered WebSocket connection: %s", name)

    async def unregister(self, name: str) -> None:
        async with self._lock:
            client = self._connections.pop(name, None)
            if client:
                await client.disconnect()

    async def get(self, name: str) -> BaseWebSocketClient | None:
        async with self._lock:
            return self._connections.get(name)

    async def connect_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name, client in self._connections.items():
            results[name] = await client.connect()
        return results

    async def disconnect_all(self) -> None:
        for _name, client in self._connections.items():
            await client.disconnect()
        self._connections.clear()

    async def health(self) -> dict[str, Any]:
        return {name: client.is_connected() for name, client in self._connections.items()}
