from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.realtime import RealtimeDataProvider
from providers.realtime.websocket.base_ws_client import BaseWebSocketClient
from providers.realtime.websocket.connection_manager import ConnectionManager
from providers.realtime.websocket.parser import WebSocketParser
from providers.realtime.websocket.reconnect import ReconnectPolicy
from providers.realtime.websocket.subscriptions import SubscriptionManager

logger = get_logger(__name__)


class WebSocketProvider(RealtimeDataProvider):
    def __init__(self, url: str = "") -> None:
        super().__init__(name="websocket")
        self.url = url
        self.client = BaseWebSocketClient(url) if url else None
        self.connection_manager = ConnectionManager()
        self.subscription_manager = SubscriptionManager()
        self.reconnect_policy = ReconnectPolicy()
        self.parser = WebSocketParser()
        self._listen_task: asyncio.Task | None = None

    async def connect(self, url: str) -> bool:
        self.url = url
        self.client = BaseWebSocketClient(url)
        return await self.client.connect()

    async def fetch(self, symbol: str | None = None, **kwargs: Any) -> Result[Any]:
        return Result.fail("WebSocket provider does not support fetch; use subscribe")

    async def get_quote(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        return Result.fail("WebSocket provider does not support direct get_quote")

    async def get_orderbook(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]:
        return Result.fail("WebSocket provider does not support direct get_orderbook")

    async def get_trades(self, symbol: str, limit: int = 100, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        return Result.fail("WebSocket provider does not support direct get_trades")

    async def subscribe(self, symbol: str, callback: Callable, **kwargs: Any) -> Result[bool]:
        if not self.client or not self.client.is_connected():
            return Result.fail("WebSocket not connected")
        self.subscription_manager.subscribe(symbol, callback)
        msg = {"type": "subscribe", "symbol": symbol}
        sent = await self.client.send(msg)
        if sent:
            logger.info("Subscribed to %s via WebSocket", symbol)
            return Result.ok(True)
        return Result.fail("Failed to send subscribe message")

    async def unsubscribe(self, symbol: str) -> Result[bool]:
        if not self.client or not self.client.is_connected():
            return Result.fail("WebSocket not connected")
        self.subscription_manager.unsubscribe(symbol)
        msg = {"type": "unsubscribe", "symbol": symbol}
        sent = await self.client.send(msg)
        return Result.ok(sent) if sent else Result.fail("Failed to send unsubscribe")

    async def _message_handler(self, message: dict[str, Any]) -> None:
        symbol = message.get("symbol", "")
        if symbol:
            await self.subscription_manager.notify(symbol, message)

    async def start_listening(self) -> None:
        if self.client:
            self._listen_task = asyncio.create_task(self.client.listen(self._message_handler))

    async def stop(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            self._listen_task = None
        if self.client:
            await self.client.disconnect()

    async def health(self) -> dict[str, Any]:
        return {
            "healthy": self.client.is_connected() if self.client else False,
            "message": "WebSocket connected"
            if self.client and self.client.is_connected()
            else "WebSocket disconnected",
            "subscriptions": self.subscription_manager.subscription_count(),
        }
