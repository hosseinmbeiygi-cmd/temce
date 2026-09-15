from __future__ import annotations

from abc import abstractmethod
from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider

logger = get_logger(__name__)


class ReferenceDataProvider(BaseProvider):
    @abstractmethod
    async def get_instrument(self, symbol: str, **kwargs: Any) -> Result[dict[str, Any]]: ...

    @abstractmethod
    async def search_instruments(self, query: str, limit: int = 20, **kwargs: Any) -> Result[list[dict[str, Any]]]: ...

    @abstractmethod
    async def get_all_instruments(self, **kwargs: Any) -> Result[list[dict[str, Any]]]: ...
