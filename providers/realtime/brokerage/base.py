from __future__ import annotations

from abc import abstractmethod
from typing import Any

from core.result import Result
from providers.base.auth import AuthHandler
from providers.base.base_provider import BaseProvider
from providers.base.http_client import HttpClient


class BaseBrokerageProvider(BaseProvider):
    def __init__(self, name: str, base_url: str, auth: AuthHandler | None = None) -> None:
        super().__init__(name=name)
        self.client = HttpClient(base_url=base_url)
        self.auth = auth or AuthHandler()

    @abstractmethod
    async def get_portfolio(self, **kwargs: Any) -> Result[Any]: ...

    @abstractmethod
    async def get_orders(self, **kwargs: Any) -> Result[Any]: ...

    @abstractmethod
    async def place_order(self, order: dict[str, Any], **kwargs: Any) -> Result[Any]: ...

    @abstractmethod
    async def get_balances(self, **kwargs: Any) -> Result[Any]: ...
