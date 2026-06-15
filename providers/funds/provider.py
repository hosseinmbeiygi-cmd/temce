from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.result import Result
from providers.base.base_provider import BaseProvider
from providers.funds.client import FundApiClient
from providers.funds.mapping import FundMapping
from providers.funds.parser import FundParser

logger = get_logger(__name__)


class FundProvider(BaseProvider):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(name="fund_provider", config=config)
        self.client = FundApiClient()
        self.parser = FundParser()
        self.mapping = FundMapping()

    async def fetch(self, **kwargs: Any) -> Result[Any]:
        return await self.get_all_funds(**kwargs)

    async def get_fund(self, fund_id: str, **kwargs: Any) -> Result[dict[str, Any]]:
        result = await self.client.get_fund_detail(fund_id)
        if not result.success:
            return Result.fail(result.error or "Failed to fetch fund detail")
        raw = result.value.text if hasattr(result.value, "text") else result.value
        parsed = self.parser.parse(raw)
        if not parsed:
            return Result.fail(f"No data for fund: {fund_id}")
        mapped = self.mapping.map_fund(parsed[0] if isinstance(parsed, list) else parsed)
        return Result.ok(mapped)

    async def get_all_funds(self, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_fund_list()
        if not result.success:
            return Result.fail(result.error or "Failed to fetch fund list")
        raw = result.value.text if hasattr(result.value, "text") else result.value
        parsed = self.parser.parse(raw)
        mapped = self.mapping.map_fund_batch(parsed)
        return Result.ok(mapped)

    async def get_nav_history(
        self, fund_id: str, start_date: str = "", end_date: str = "", **kwargs: Any
    ) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_fund_nav_history(fund_id, start_date, end_date)
        if not result.success:
            return Result.fail(result.error or "Failed to fetch NAV history")
        raw = result.value.text if hasattr(result.value, "text") else result.value
        parsed = self.parser.parse_nav(raw)
        mapped = self.mapping.map_nav_batch(parsed)
        return Result.ok(mapped)

    async def get_holdings(self, fund_id: str, **kwargs: Any) -> Result[list[dict[str, Any]]]:
        result = await self.client.get_fund_holdings(fund_id)
        if not result.success:
            return Result.fail(result.error or "Failed to fetch holdings")
        raw = result.value.text if hasattr(result.value, "text") else result.value
        parsed = self.parser.parse_holdings(raw)
        mapped = self.mapping.map_holdings_batch(parsed)
        return Result.ok(mapped)

    async def health(self) -> dict[str, Any]:
        result = await self.client.get_fund_list()
        return {"healthy": result.success, "message": "ok" if result.success else result.error}
