from __future__ import annotations

from abc import abstractmethod
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider


class MacroDataProvider(BaseProvider):
    @abstractmethod
    async def fetch_latest(self, **kwargs: Any) -> Result[dict[str, Any]]: ...

    @abstractmethod
    async def fetch_history(self, days: int = 365, **kwargs: Any) -> Result[list[dict[str, Any]]]: ...
