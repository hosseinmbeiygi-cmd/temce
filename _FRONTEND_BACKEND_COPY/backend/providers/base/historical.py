from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
from typing import Any

from core.result import Result
from providers.base.base_provider import BaseProvider


class HistoricalDataProvider(BaseProvider):
    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        **kwargs: Any,
    ) -> Result[list[dict[str, Any]]]: ...

    @abstractmethod
    async def get_daily_summary(
        self, symbol: str, date: datetime | None = None, **kwargs: Any
    ) -> Result[dict[str, Any]]: ...
