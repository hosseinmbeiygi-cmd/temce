from __future__ import annotations

from abc import abstractmethod
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider


class ManualDataProvider(BaseProvider):
    @abstractmethod
    async def submit(self, data: dict[str, Any], **kwargs: Any) -> Result[dict[str, Any]]: ...

    @abstractmethod
    async def validate(self, data: dict[str, Any]) -> Result[bool]: ...

    @abstractmethod
    async def get_pending(self) -> Result[list[dict[str, Any]]]: ...
