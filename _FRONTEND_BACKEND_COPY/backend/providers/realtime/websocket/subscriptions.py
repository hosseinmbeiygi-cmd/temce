from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionManager:
    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Callable]] = {}
        self._symbol_subscriptions: dict[str, list[str]] = {}

    def subscribe(self, symbol: str, callback: Callable, subscriber_id: str = "default") -> None:
        if symbol not in self._subscriptions:
            self._subscriptions[symbol] = []
        self._subscriptions[symbol].append(callback)
        self._symbol_subscriptions.setdefault(subscriber_id, []).append(symbol)
        logger.info("Subscribed %s to %s", subscriber_id, symbol)

    def unsubscribe(self, symbol: str, subscriber_id: str = "default") -> None:
        if subscriber_id in self._symbol_subscriptions and symbol in self._symbol_subscriptions[subscriber_id]:
            self._symbol_subscriptions[subscriber_id].remove(symbol)
        self._subscriptions.pop(symbol, None)
        logger.info("Unsubscribed %s from %s", subscriber_id, symbol)

    def unsubscribe_all(self, subscriber_id: str = "default") -> None:
        symbols = self._symbol_subscriptions.pop(subscriber_id, [])
        for symbol in symbols:
            self._subscriptions.pop(symbol, None)
        logger.info("Unsubscribed %s from all", subscriber_id)

    def get_subscribers(self, symbol: str) -> list[Callable]:
        return self._subscriptions.get(symbol, [])

    async def notify(self, symbol: str, data: Any) -> None:
        for callback in self.get_subscribers(symbol):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error("Subscription callback failed for %s: %s", symbol, e)

    def list_subscriptions(self) -> dict[str, list[str]]:
        return {s: list(cbs) for s, cbs in self._subscriptions.items()}

    def subscription_count(self) -> int:
        return len(self._subscriptions)
