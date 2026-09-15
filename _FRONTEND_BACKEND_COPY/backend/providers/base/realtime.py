from __future__ import annotations

from abc import abstractmethod
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider


class RealtimeDataProvider(BaseProvider):
    @abstractmethod
    async def get_quote(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]: ...

    @abstractmethod
    async def get_orderbook(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]: ...

    @abstractmethod
    async def get_trades(self, symbol: str, limit: int = 100, **kwargs: Any) -> Result[list[dict[str, Any]]]: ...

    @abstractmethod
    async def subscribe(self, symbol: str, callback: Any, **kwargs: Any) -> Result[bool]: ...

    @abstractmethod
    async def unsubscribe(self, symbol: str) -> Result[bool]: ...
